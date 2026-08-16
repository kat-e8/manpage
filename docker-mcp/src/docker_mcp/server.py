import asyncio
import signal
import sys
from typing import List, Dict, Any
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
import mcp.server.stdio
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.types import Receive, Scope, Send
from .handlers import DockerHandlers

server = Server("docker-mcp")


@server.list_prompts()
async def handle_list_prompts() -> List[types.Prompt]:
    return [
        types.Prompt(
            name="deploy-stack",
            description="Generate and deploy a Docker stack based on requirements",
            arguments=[
                types.PromptArgument(
                    name="requirements",
                    description="Description of the desired Docker stack",
                    required=True
                ),
                types.PromptArgument(
                    name="project_name",
                    description="Name for the Docker Compose project",
                    required=True
                )
            ]
        )
    ]


@server.get_prompt()
async def handle_get_prompt(name: str, arguments: Dict[str, str] | None) -> types.GetPromptResult:
    if name != "deploy-stack":
        raise ValueError(f"Unknown prompt: {name}")

    if not arguments or "requirements" not in arguments or "project_name" not in arguments:
        raise ValueError("Missing required arguments")

    system_message = (
        "You are a Docker deployment specialist. Generate appropriate Docker Compose YAML or "
        "container configurations based on user requirements. For simple single-container "
        "deployments, use the create-container tool. For multi-container deployments, generate "
        "a docker-compose.yml and use the deploy-compose tool. To access logs, first use the "
        "list-containers tool to discover running containers, then use the get-logs tool to "
        "retrieve logs for a specific container."
    )

    user_message = f"""Please help me deploy the following stack:
Requirements: {arguments['requirements']}
Project name: {arguments['project_name']}

Analyze if this needs a single container or multiple containers. Then:
1. For single container: Use the create-container tool with format:
{{
    "image": "image-name",
    "name": "container-name",
    "ports": {{"80": "80"}},
    "environment": {{"ENV_VAR": "value"}}
}}

2. For multiple containers: Use the deploy-compose tool with format:
{{
    "project_name": "example-stack",
    "compose_yaml": "version: '3.8'\\nservices:\\n  service1:\\n    image: image1:latest\\n    ports:\\n      - '8080:80'"
}}"""

    return types.GetPromptResult(
        description="Generate and deploy a Docker stack",
        messages=[
            types.PromptMessage(
                role="system",
                content=types.TextContent(
                    type="text",
                    text=system_message
                )
            ),
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=user_message
                )
            )
        ]
    )


DOCKER_HOST_PROPERTY = {
    "type": "string",
    "description": (
        "Override which Docker Engine this call targets, e.g. "
        "'ssh://user@remote-host'. Omit to use the server's default engine "
        "(the local engine / whatever DOCKER_HOST is set in its environment). "
        "Only the ssh:// scheme is supported -- TCP+TLS targets would require "
        "passing certificate/key material as a tool argument."
    )
}


@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="create-container",
            description="Create a new standalone Docker container",
            inputSchema={
                "type": "object",
                "properties": {
                    "image": {"type": "string"},
                    "name": {"type": "string"},
                    "ports": {
                        "type": "object",
                        "additionalProperties": {"type": "string"}
                    },
                    "environment": {
                        "type": "object",
                        "additionalProperties": {"type": "string"}
                    },
                    "docker_host": DOCKER_HOST_PROPERTY
                },
                "required": ["image"]
            }
        ),
        types.Tool(
            name="deploy-compose",
            description="Deploy a Docker Compose stack",
            inputSchema={
                "type": "object",
                "properties": {
                    "compose_yaml": {"type": "string"},
                    "project_name": {"type": "string"},
                    "docker_host": DOCKER_HOST_PROPERTY
                },
                "required": ["compose_yaml", "project_name"]
            }
        ),
        types.Tool(
            name="get-logs",
            description="Retrieve the latest logs for a specified Docker container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_name": {"type": "string"},
                    "docker_host": DOCKER_HOST_PROPERTY
                },
                "required": ["container_name"]
            }
        ),
        types.Tool(
            name="list-containers",
            description="List all Docker containers",
            inputSchema={
                "type": "object",
                "properties": {
                    "docker_host": DOCKER_HOST_PROPERTY
                }
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any] | None) -> List[types.TextContent]:
    if not arguments and name != "list-containers":
        raise ValueError("Missing arguments")

    try:
        if name == "create-container":
            return await DockerHandlers.handle_create_container(arguments)
        elif name == "deploy-compose":
            return await DockerHandlers.handle_deploy_compose(arguments)
        elif name == "get-logs":
            return await DockerHandlers.handle_get_logs(arguments)
        elif name == "list-containers":
            return await DockerHandlers.handle_list_containers(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)} | Arguments: {arguments}")]


async def main():
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="docker-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


class _StreamableHTTPASGIApp:
    """Thin ASGI wrapper around a StreamableHTTPSessionManager.

    Kept as a plain callable class (not a function) so Starlette's Route
    treats it as a raw ASGI app instead of wrapping it as a request/response
    handler, which would break the SSE streaming the transport relies on.
    """

    def __init__(self, session_manager: StreamableHTTPSessionManager) -> None:
        self.session_manager = session_manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.session_manager.handle_request(scope, receive, send)


def create_streamable_http_app(*, json_response: bool = False, stateless: bool = False) -> Starlette:
    """Build an ASGI app serving docker-mcp over streamable HTTP at /mcp.

    Standalone use: pass to `uvicorn.run(...)`. To mount under a gateway
    (e.g. FastAPI's `app.mount("/docker", ...)`), the mounted app's lifespan
    must still run so the underlying StreamableHTTPSessionManager starts —
    Starlette/FastAPI do not do this automatically for mounted sub-apps.

    The SDK's default DNS-rebinding protection only allows Host: localhost/
    127.0.0.1, which rejects every request arriving via a reverse-proxying
    gateway (Host: docker-mcp:8008, the real internal service name). Kept
    enabled rather than disabled outright, with the internal service name
    allow-listed explicitly: this is meant to run with no published host
    port, reachable only from other containers on its compose network, so
    that's the actual trusted-caller identity, not an open door.
    """
    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=json_response,
        stateless=stateless,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["docker-mcp:8008", "localhost:8008", "127.0.0.1:8008"],
            allowed_origins=[
                "http://docker-mcp:8008", "http://localhost:8008", "http://127.0.0.1:8008",
            ],
        ),
    )

    return Starlette(
        routes=[Route("/mcp", endpoint=_StreamableHTTPASGIApp(session_manager))],
        lifespan=lambda app: session_manager.run(),
    )


def handle_shutdown(signum, frame):
    print("Shutting down gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
