"""Community goal tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import map_tebex_errors


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="list_community_goals",
        description="List all community goals with target, progress, status, and times achieved.",
    )
    @map_tebex_errors
    async def list_community_goals() -> Any:
        return await ctx.client.list_community_goals()

    @mcp.tool(
        name="get_community_goal",
        description="Get community goal details by ID.",
    )
    @map_tebex_errors
    async def get_community_goal(
        goal_id: Annotated[int, Field(description="Community goal ID", ge=1)],
    ) -> Any:
        return await ctx.client.get_community_goal(goal_id)
