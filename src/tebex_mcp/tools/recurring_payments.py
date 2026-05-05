"""Recurring payment (subscription) tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import (
    DESTRUCTIVE,
    IDEMPOTENT,
    READ_ONLY,
    map_tebex_errors,
    ok,
)


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="list_recurring_payments",
        description=(
            "List all recurring payments (subscriptions) on the store: "
            "reference, status, amount, interval, next due date, customer."
        ),
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def list_recurring_payments() -> Any:
        return await ctx.client.list_recurring_payments()

    @mcp.tool(
        name="get_recurring_payment",
        description="Get details of a single recurring payment by its reference.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_recurring_payment(
        reference: Annotated[
            str,
            Field(
                description="Recurring payment reference (e.g. 'rp-abc123')",
                min_length=1,
            ),
        ],
    ) -> Any:
        return await ctx.client.get_recurring_payment(reference)

    @mcp.tool(
        name="cancel_recurring_payment",
        description=(
            "Cancel a recurring payment. The customer is no longer billed; "
            "their existing access stays until the current period ends. "
            "Cannot be undone — to restart, the customer must subscribe again."
        ),
        annotations=DESTRUCTIVE,
    )
    @map_tebex_errors
    async def cancel_recurring_payment(
        reference: Annotated[
            str, Field(description="Recurring payment reference", min_length=1)
        ],
    ) -> dict[str, Any]:
        await ctx.client.cancel_recurring_payment(reference)
        return ok(reference=reference, status="Cancelled")

    @mcp.tool(
        name="pause_recurring_payment",
        description=(
            "Pause a recurring payment for a number of months. Billing resumes "
            "automatically afterwards. Use to honour temporary stop requests."
        ),
        annotations=IDEMPOTENT,
    )
    @map_tebex_errors
    async def pause_recurring_payment(
        reference: Annotated[
            str, Field(description="Recurring payment reference", min_length=1)
        ],
        months: Annotated[
            int,
            Field(description="Number of months to pause for", ge=1, le=12),
        ],
    ) -> dict[str, Any]:
        await ctx.client.pause_recurring_payment(reference, months)
        return ok(reference=reference, status="Paused", paused_months=months)

    @mcp.tool(
        name="reactivate_recurring_payment",
        description=(
            "Reactivate a paused recurring payment immediately, before the "
            "pause window ends."
        ),
        annotations=IDEMPOTENT,
    )
    @map_tebex_errors
    async def reactivate_recurring_payment(
        reference: Annotated[
            str, Field(description="Recurring payment reference", min_length=1)
        ],
    ) -> dict[str, Any]:
        await ctx.client.reactivate_recurring_payment(reference)
        return ok(reference=reference, status="Active")
