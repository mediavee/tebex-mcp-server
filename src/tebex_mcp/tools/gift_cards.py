"""Gift card tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import (
    DESTRUCTIVE,
    READ_ONLY,
    WRITE,
    map_tebex_errors,
    ok,
)


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="list_gift_cards",
        description="List all gift cards with id, code, balance, note, and void status.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def list_gift_cards() -> Any:
        return await ctx.client.list_gift_cards()

    @mcp.tool(
        name="get_gift_card",
        description="Get gift card details by ID.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_gift_card(
        gift_card_id: Annotated[int, Field(description="Gift card ID", ge=1)],
    ) -> Any:
        return await ctx.client.get_gift_card(gift_card_id)

    @mcp.tool(
        name="lookup_gift_card",
        description="Look up a gift card by its customer-facing code.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def lookup_gift_card(
        code: Annotated[str, Field(description="Gift card code", min_length=1)],
    ) -> Any:
        return await ctx.client.lookup_gift_card(code)

    @mcp.tool(
        name="create_gift_card",
        description="Create a gift card with amount, expiration, and note.",
        annotations=WRITE,
    )
    @map_tebex_errors
    async def create_gift_card(
        amount: Annotated[
            float, Field(description="Gift card value in store currency", ge=0)
        ],
        expires_at: Annotated[
            str, Field(description="Expiration date in ISO 8601 format (e.g. 2025-12-31)")
        ],
        note: Annotated[str, Field(description="Internal note for this gift card")],
    ) -> Any:
        return await ctx.client.create_gift_card(
            amount=amount, expires_at=expires_at, note=note
        )

    @mcp.tool(
        name="topup_gift_card",
        description="Add funds to a gift card.",
        annotations=WRITE,
    )
    @map_tebex_errors
    async def topup_gift_card(
        gift_card_id: Annotated[int, Field(description="Gift card ID", ge=1)],
        amount: Annotated[float, Field(description="Amount to add in store currency", ge=0)],
    ) -> Any:
        return await ctx.client.topup_gift_card(gift_card_id, amount)

    @mcp.tool(
        name="void_gift_card",
        description="Void a gift card. IRREVERSIBLE — remaining balance becomes unusable.",
        annotations=DESTRUCTIVE,
    )
    @map_tebex_errors
    async def void_gift_card(
        gift_card_id: Annotated[int, Field(description="Gift card ID", ge=1)],
    ) -> dict[str, Any]:
        await ctx.client.void_gift_card(gift_card_id)
        return ok(gift_card_id=gift_card_id, voided=True)
