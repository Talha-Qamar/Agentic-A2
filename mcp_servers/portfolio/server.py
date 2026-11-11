"""GigBid Portfolio MCP server (read-only), built with the official MCP Python SDK (FastMCP).

    gigbid-portfolio-mcp                          # stdio, portfolio from $PORTFOLIO_DIR (Claude Desktop / Cursor)
    gigbid-portfolio-mcp --transport http --port 8201
    python -m mcp_servers.portfolio.server --transport http   # inside the GigBid repo (uses GigBid RAG)

HTTP transport accepts an optional bearer token (PORTFOLIO_MCP_TOKEN).
"""
from __future__ import annotations

import argparse
import os

from mcp.server.fastmcp import FastMCP

from . import prompts, resources, tools
from .backend import make_backend

INSTRUCTIONS = ("Read-only access to one freelancer's portfolio: case studies, repositories and code, CV, client reviews "
                "and past proposals labelled won/replied/ignored. Use match_requirements to map a job's requirements to "
                "evidence, search_evidence for one requirement, get_case_study for full text. Never claim experience "
                "that these tools do not return.")


def build_server(backend=None, toolset: str | None = None, **kw) -> FastMCP:
    backend = backend or make_backend()
    mcp = FastMCP("gigbid-portfolio", instructions=INSTRUCTIONS, stateless_http=True, json_response=True, **kw)
    tools.register(mcp, backend, toolset)
    resources.register(mcp, backend)
    prompts.register(mcp)
    mcp._gigbid_backend = backend
    return mcp


def http_app(mcp: FastMCP | None = None, token: str | None = None):
    """Streamable-HTTP ASGI app with optional bearer auth."""
    from starlette.responses import JSONResponse
    mcp = mcp or build_server()
    app = mcp.streamable_http_app()
    token = token if token is not None else os.environ.get("PORTFOLIO_MCP_TOKEN")
    if not token:
        return app

    async def guarded(scope, receive, send):
        if scope["type"] == "http":
            auth = dict(scope.get("headers", [])).get(b"authorization", b"").decode()
            if auth != f"Bearer {token}":
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        await app(scope, receive, send)
    guarded.router = app.router  # expose lifespan for mounting
    return guarded


def main() -> None:
    ap = argparse.ArgumentParser(description="GigBid Portfolio MCP server")
    ap.add_argument("--transport", choices=["stdio", "http"], default=os.environ.get("MCP_TRANSPORT", "stdio"))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8201")))
    ap.add_argument("--portfolio-dir", default=None, help="folder with cv.pdf, case_studies/, repos/, reviews.json ...")
    a = ap.parse_args()
    if a.portfolio_dir:
        os.environ["PORTFOLIO_DIR"] = a.portfolio_dir
    if a.transport == "stdio":
        build_server().run("stdio")
    else:
        import uvicorn
        uvicorn.run(http_app(), host=a.host, port=a.port)


if __name__ == "__main__":
    main()
