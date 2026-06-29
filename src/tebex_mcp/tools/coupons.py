"""Coupon tools."""

from __future__ import annotations

from typing import Annotated, Any, Literal

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
        name="list_coupons",
        description=(
            "List coupons (code, discount, scope, expiry, usage). Paginated: "
            "`pagination` has `currentPage`/`lastPage`/`next`; pass `page` for more."
        ),
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def list_coupons(
        page: Annotated[
            int | None, Field(description="Page number (1-indexed, default: 1)", ge=1)
        ] = None,
    ) -> Any:
        return await ctx.client.list_coupons(page)

    @mcp.tool(
        name="get_coupon",
        description="Get coupon details by ID.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_coupon(
        coupon_id: Annotated[int, Field(description="Coupon ID", ge=1)],
    ) -> Any:
        return await ctx.client.get_coupon(coupon_id)

    @mcp.tool(
        name="create_coupon",
        description="Create a coupon: code, discount type, scope, limits, date range.",
        annotations=WRITE,
    )
    @map_tebex_errors
    async def create_coupon(
        code: Annotated[str, Field(description="Code customers enter", min_length=1)],
        effective_on: Annotated[
            Literal["package", "category", "cart"],
            Field(description="What the coupon applies to"),
        ],
        discount_type: Annotated[
            Literal["value", "percentage"],
            Field(description="Fixed value or percentage"),
        ],
        redeem_unlimited: Annotated[bool, Field(description="Redeemable unlimited times")],
        expire_never: Annotated[bool, Field(description="Never expires")],
        basket_type: Annotated[
            Literal["single", "subscription", "both"],
            Field(description="Applicable basket types"),
        ],
        minimum: Annotated[float, Field(description="Min basket value to apply", ge=0)],
        discount_application_method: Annotated[
            int,
            Field(
                description="0 = each package, 1 = basket total, 2 = most expensive item",
                ge=0,
                le=2,
            ),
        ],
        packages: Annotated[
            list[int] | None,
            Field(description="Package IDs (when effective_on=package)"),
        ] = None,
        categories: Annotated[
            list[int] | None,
            Field(description="Category IDs (when effective_on=category)"),
        ] = None,
        discount_amount: Annotated[
            float | None,
            Field(description="Amount (when discount_type=value)", ge=0),
        ] = None,
        discount_percentage: Annotated[
            float | None,
            Field(description="Percent (when discount_type=percentage)", ge=0, le=100),
        ] = None,
        expire_limit: Annotated[
            int | None,
            Field(description="Max redemptions (when redeem_unlimited=false)", ge=1),
        ] = None,
        expire_date: Annotated[
            str | None, Field(description="Expiry date (when expire_never=false)")
        ] = None,
        start_date: Annotated[str | None, Field(description="Start date")] = None,
        username: Annotated[str | None, Field(description="Restrict to one username")] = None,
        note: Annotated[str | None, Field(description="Internal note")] = None,
    ) -> Any:
        return await ctx.client.create_coupon(
            {
                "code": code,
                "effective_on": effective_on,
                "packages": packages,
                "categories": categories,
                "discount_type": discount_type,
                "discount_amount": discount_amount,
                "discount_percentage": discount_percentage,
                "redeem_unlimited": redeem_unlimited,
                "expire_never": expire_never,
                "expire_limit": expire_limit,
                "expire_date": expire_date,
                "start_date": start_date,
                "basket_type": basket_type,
                "minimum": minimum,
                "discount_application_method": discount_application_method,
                "username": username,
                "note": note,
            }
        )

    @mcp.tool(
        name="delete_coupon",
        description="Delete a coupon. The code becomes unredeemable.",
        annotations=DESTRUCTIVE,
    )
    @map_tebex_errors
    async def delete_coupon(
        coupon_id: Annotated[int, Field(description="Coupon ID", ge=1)],
    ) -> dict[str, Any]:
        await ctx.client.delete_coupon(coupon_id)
        return ok(coupon_id=coupon_id, deleted=True)
