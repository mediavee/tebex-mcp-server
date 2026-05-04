"""Store information tool."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import map_tebex_errors


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="get_store_info",
        description="Get store and server info: id, name, domain, currency, game type, online mode.",
    )
    @map_tebex_errors
    async def get_store_info() -> Any:
        return await ctx.client.get_information()
