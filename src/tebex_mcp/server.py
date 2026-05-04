"""FastMCP application wiring: lifespan, custom routes, auth, transport."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import uvicorn
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount

from tebex_mcp import __version__
from tebex_mcp.auth import bearer_auth
from tebex_mcp.client import TebexClient, current_secret
from tebex_mcp.config import Settings, load_settings
from tebex_mcp.context import ToolContext
from tebex_mcp.logging import configure_logging, get_logger
from tebex_mcp.tools import register_all

log = get_logger(__name__)


def build_mcp(settings: Settings) -> tuple[FastMCP, TebexClient]:
    """Build the FastMCP server, register tools and the health route."""

    client = TebexClient(settings)
    ctx = ToolContext(settings=settings, client=client)

    mcp = FastMCP(
        name="tebex-mcp",
        version=__version__,
        instructions=(
            "Operate a Tebex store: packages, payments, gift cards, coupons, "
            "bans, community goals, command queue, player lookups."
        ),
    )
    register_all(mcp, ctx)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "version": __version__})

    return mcp, client


def build_asgi_app(settings: Settings) -> Starlette:
    """Build the full ASGI app: FastMCP + bearer auth + client lifespan."""

    mcp, client = build_mcp(settings)

    # FastMCP 3.x returns a fully-formed Starlette app rooted at ``path``.
    # Wrap it in a parent Starlette so we can layer bearer auth across every
    # route and chain the http client's lifespan with FastMCP's session manager.
    mcp_app = mcp.http_app(path="/mcp")

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with mcp_app.router.lifespan_context(app):
            log.info(
                "tebex_mcp_started",
                version=__version__,
                tebex_base=client.BASE_URL,
                log_level=settings.log_level,
                log_json=settings.log_json,
                secret_source="per_request_header",
            )
            try:
                yield
            finally:
                log.info("tebex_mcp_shutting_down")
                await client.aclose()

    expected_token = settings.mcp_auth_token.get_secret_value()
    return Starlette(
        routes=[Mount("/", app=mcp_app)],
        middleware=[Middleware(_AuthMiddleware, expected_token=expected_token)],
        lifespan=lifespan,
    )


class _AuthMiddleware(BaseHTTPMiddleware):
    """Bearer-token + per-request Tebex secret gate. Skipped on /healthz."""

    def __init__(self, app, expected_token: str) -> None:
        super().__init__(app)
        self._guard = bearer_auth(expected_token)

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/healthz":
            return await call_next(request)

        async def with_secret(req: Request) -> Response:
            secret = req.headers.get("x-tebex-secret", "").strip()
            if not secret:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": (
                                "Missing X-Tebex-Secret header. Configure your MCP "
                                "client to send the per-store Tebex Plugin API "
                                "secret on every request."
                            ),
                        },
                        "id": None,
                    },
                    status_code=400,
                )
            token = current_secret.set(secret)
            try:
                return await call_next(req)
            finally:
                current_secret.reset(token)

        return await self._guard(request, with_secret)


async def run() -> None:
    settings = load_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    app = build_asgi_app(settings)

    config = uvicorn.Config(
        app,
        host=settings.http_host,
        port=settings.http_port,
        log_config=None,  # let structlog/stdlib bridge handle uvicorn logs
        access_log=False,
        timeout_graceful_shutdown=10,
    )
    server = uvicorn.Server(config)

    log.info(
        "tebex_mcp_listening",
        host=settings.http_host,
        port=settings.http_port,
        mcp_url=f"http://{settings.http_host}:{settings.http_port}/mcp",
    )
    with contextlib.suppress(asyncio.CancelledError):
        await server.serve()
