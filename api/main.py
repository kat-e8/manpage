"""
Generic MCP gateway -- not coder-commands-specific, despite living in this
project. Reverse-proxies /coder-commands-mcp/* to the coder-commands-mcp
service, /docker-mcp/* to the docker-mcp service, and /postgres-mcp/* to the
postgres-mcp service -- all three Streamable HTTP -- giving the system one
external entry point and a place to add auth/logging later without touching
any individual server's logic. Meant to keep mounting whatever MCP servers
this project ends up with; adding one is a new upstream + proxy route here,
nothing about this gateway's own identity.

The MCP Streamable HTTP transport is stateful and can stream (SSE) --
this is a real byte-level reverse proxy (method, headers, body, and the
response stream all forwarded as-is), not a JSON-in/JSON-out relay.
"""
from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

CODER_COMMANDS_MCP_UPSTREAM_URL = os.environ.get(
    "CODER_COMMANDS_MCP_UPSTREAM_URL", "http://coder-commands-mcp:9000"
)
POSTGRES_MCP_UPSTREAM_URL = os.environ.get(
    "POSTGRES_MCP_UPSTREAM_URL", "http://postgres-mcp:8000"
)
DOCKER_MCP_UPSTREAM_URL = os.environ.get(
    "DOCKER_MCP_UPSTREAM_URL", "http://docker-mcp:8008"
)

# Fail closed: with docker-mcp behind this proxy holding the host's Docker
# socket, an unset key must deny every proxied request rather than silently
# running open. /healthz is exempt so the compose healthcheck keeps working
# without needing the key.
GATEWAY_API_KEY = os.environ.get("GATEWAY_API_KEY")


async def require_api_key(request: Request) -> None:
    supplied = request.headers.get("x-api-key", "")
    if not GATEWAY_API_KEY or not hmac.compare_digest(supplied, GATEWAY_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")

# Headers that are per-hop, not meaningful to forward across a proxy.
HOP_BY_HOP = {
    "connection", "keep-alive", "transfer-encoding", "upgrade",
    "proxy-authenticate", "proxy-authorization", "te", "trailers", "host",
}

_cc_client: httpx.AsyncClient
_pg_client: httpx.AsyncClient
_docker_client: httpx.AsyncClient


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _cc_client, _pg_client, _docker_client
    _cc_client = httpx.AsyncClient(base_url=CODER_COMMANDS_MCP_UPSTREAM_URL, timeout=None)
    _pg_client = httpx.AsyncClient(base_url=POSTGRES_MCP_UPSTREAM_URL, timeout=None)
    _docker_client = httpx.AsyncClient(base_url=DOCKER_MCP_UPSTREAM_URL, timeout=None)
    yield
    await _cc_client.aclose()
    await _pg_client.aclose()
    await _docker_client.aclose()


app = FastAPI(title="MCP Gateway", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.api_route(
    "/coder-commands-mcp{path:path}",
    methods=["GET", "POST", "DELETE"],
    dependencies=[Depends(require_api_key)],
)
async def proxy_coder_commands_mcp(path: str, request: Request):
    url = f"/mcp{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
    body = await request.body()

    upstream_req = _cc_client.build_request(
        request.method, url, headers=headers, content=body, params=request.query_params,
    )
    upstream_resp = await _cc_client.send(upstream_req, stream=True)

    resp_headers = {k: v for k, v in upstream_resp.headers.items() if k.lower() not in HOP_BY_HOP}

    return StreamingResponse(
        upstream_resp.aiter_raw(),
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        background=BackgroundTask(upstream_resp.aclose),
    )


@app.api_route(
    "/docker-mcp{path:path}",
    methods=["GET", "POST", "DELETE"],
    dependencies=[Depends(require_api_key)],
)
async def proxy_docker_mcp(path: str, request: Request):
    # docker-mcp is Streamable HTTP too (single /mcp endpoint, no separate
    # /messages side-channel), same shape as proxy_mcp and proxy_postgres_mcp.
    url = f"/mcp{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
    body = await request.body()

    upstream_req = _docker_client.build_request(
        request.method, url, headers=headers, content=body, params=request.query_params,
    )
    upstream_resp = await _docker_client.send(upstream_req, stream=True)

    resp_headers = {k: v for k, v in upstream_resp.headers.items() if k.lower() not in HOP_BY_HOP}

    return StreamingResponse(
        upstream_resp.aiter_raw(),
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        background=BackgroundTask(upstream_resp.aclose),
    )


@app.api_route(
    "/postgres-mcp{path:path}",
    methods=["GET", "POST", "DELETE"],
    dependencies=[Depends(require_api_key)],
)
async def proxy_postgres_mcp(path: str, request: Request):
    # postgres-mcp is Streamable HTTP (single /mcp endpoint, no separate
    # /messages side-channel), so this mirrors proxy_docker_mcp.
    url = f"/mcp{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
    body = await request.body()

    upstream_req = _pg_client.build_request(
        request.method, url, headers=headers, content=body, params=request.query_params,
    )
    upstream_resp = await _pg_client.send(upstream_req, stream=True)

    resp_headers = {k: v for k, v in upstream_resp.headers.items() if k.lower() not in HOP_BY_HOP}

    return StreamingResponse(
        upstream_resp.aiter_raw(),
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        background=BackgroundTask(upstream_resp.aclose),
    )
