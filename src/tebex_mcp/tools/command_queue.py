"""Command queue tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import IDEMPOTENT, READ_ONLY, map_tebex_errors, ok


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="get_command_queue",
        description="Get due player command queue: players with pending commands, next check interval.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_command_queue() -> Any:
        return await ctx.client.get_command_queue()

    @mcp.tool(
        name="get_offline_commands",
        description="Get commands executable without the player online: id, string, payment, package, conditions.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_offline_commands() -> Any:
        return await ctx.client.get_offline_commands()

    @mcp.tool(
        name="get_online_commands",
        description="Get pending commands for a specific player (requires player online).",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_online_commands(
        player_id: Annotated[int, Field(description="Tebex player ID", ge=1)],
    ) -> Any:
        return await ctx.client.get_online_commands(player_id)

    @mcp.tool(
        name="delete_commands",
        description="Remove executed commands from the queue.",
        annotations=IDEMPOTENT,
    )
    @map_tebex_errors
    async def delete_commands(
        ids: Annotated[
            list[int],
            Field(description="Command IDs to remove", min_length=1),
        ],
    ) -> dict[str, Any]:
        await ctx.client.delete_commands(ids)
        return ok(deleted_count=len(ids), ids=ids)
