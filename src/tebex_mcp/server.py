"""FastMCP application wiring (stdio transport, single tenant)."""

from __future__ import annotations

from fastmcp import FastMCP

from tebex_mcp import __version__
from tebex_mcp.client import TebexClient
from tebex_mcp.config import Settings, load_settings
from tebex_mcp.context import ToolContext
from tebex_mcp.logging import configure_logging, get_logger
from tebex_mcp.tools import register_all

log = get_logger(__name__)


def build_mcp(settings: Settings) -> tuple[FastMCP, TebexClient]:
    """Build the FastMCP server and register every tool."""
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
    return mcp, client


async def run_async() -> None:
    settings = load_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    mcp, client = build_mcp(settings)
    log.info(
        "tebex_mcp_started",
        version=__version__,
        tebex_base=client.BASE_URL,
        log_level=settings.log_level,
        log_json=settings.log_json,
    )
    try:
        await mcp.run_async()
    finally:
        log.info("tebex_mcp_shutting_down")
        await client.aclose()
