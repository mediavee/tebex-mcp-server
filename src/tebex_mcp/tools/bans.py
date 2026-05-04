"""Ban tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import map_tebex_errors


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="list_bans",
        description="List all bans with id, time, ip, email, reason, and user info.",
    )
    @map_tebex_errors
    async def list_bans() -> Any:
        return await ctx.client.list_bans()

    @mcp.tool(
        name="create_ban",
        description="Ban a user or IP from the store.",
    )
    @map_tebex_errors
    async def create_ban(
        reason: Annotated[str, Field(description="Reason for the ban", min_length=1)],
        ip: Annotated[str | None, Field(description="IP address to ban")] = None,
        user: Annotated[
            str | None, Field(description="Username or UUID of the player to ban")
        ] = None,
    ) -> Any:
        return await ctx.client.create_ban(reason=reason, ip=ip, user=user)
