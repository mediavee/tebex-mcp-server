"""Sales tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import READ_ONLY, map_tebex_errors


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="list_sales",
        description="List active sales with scope, discount, and start/expire dates.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def list_sales() -> Any:
        return await ctx.client.list_sales()
