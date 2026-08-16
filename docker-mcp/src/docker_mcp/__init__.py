from . import server
import argparse
import asyncio

def main():
    """Main entry point for the package."""
    parser = argparse.ArgumentParser(description="docker-mcp: MCP server for Docker operations")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport to use (default: stdio, for Claude Desktop/uvx subprocess mode)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (streamable-http only)")
    parser.add_argument("--port", type=int, default=8008, help="Port to bind (streamable-http only)")
    args = parser.parse_args()

    if args.transport == "streamable-http":
        import uvicorn

        uvicorn.run(server.create_streamable_http_app(), host=args.host, port=args.port)
    else:
        asyncio.run(server.main())

# Optionally expose other important items at package level
__all__ = ['main', 'server']