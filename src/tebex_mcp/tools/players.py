"""Player tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from tebex_mcp import normalize
from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import READ_ONLY, map_tebex_errors


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="lookup_player",
        description=(
            "Look up a player by username or UUID: bans, chargeback rate, payments "
            "(each with its `tbx-…` transaction_id), purchase totals. The only source "
            "of transaction ids for get/update_payment. Ultimate plan only."
        ),
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def lookup_player(
        identifier: Annotated[str, Field(description="Player username or UUID", min_length=1)],
    ) -> dict[str, Any]:
        return normalize.player_profile(await ctx.client.lookup_player(identifier))

    @mcp.tool(
        name="get_player_packages",
        description="List active packages owned by a player. Optionally filter by package ID.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_player_packages(
        player_id: Annotated[
            int, Field(description="Tebex player ID (from lookup_player)", ge=1)
        ],
        package_id: Annotated[
            int | None, Field(description="Filter to a specific package ID", ge=1)
        ] = None,
    ) -> Any:
        return await ctx.client.get_player_packages(player_id, package_id)
