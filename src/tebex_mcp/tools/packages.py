"""Package tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from tebex_mcp import normalize
from tebex_mcp.client import TebexError
from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import IDEMPOTENT, READ_ONLY, map_tebex_errors, ok


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="list_categories",
        description="List all categories with nested package summaries.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def list_categories() -> Any:
        return await ctx.client.get_listing()

    @mcp.tool(
        name="list_packages",
        description="List all packages: id, name, price, type, category, expiry, limits, disabled.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def list_packages() -> Any:
        return await ctx.client.list_packages()

    @mcp.tool(
        name="get_package",
        description=(
            "Get a package's full config: price, type, category, expiry, limits, "
            "GUI item, server/requirement rules. Set include_description to also "
            "fetch the storefront view (description, tax-inclusive pricing, media, "
            "options) under a `storefront` key — one extra Headless API call."
        ),
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_package(
        package_id: Annotated[int, Field(description="Package ID", ge=1)],
        include_description: Annotated[
            bool,
            Field(description="Also fetch the storefront description/pricing/media"),
        ] = False,
    ) -> Any:
        pkg = await ctx.client.get_package(package_id)
        if include_description and isinstance(pkg, dict):
            try:
                storefront = normalize.package_storefront(
                    await ctx.client.get_package_storefront(package_id)
                )
            except TebexError:
                storefront = {"error": "not available on the storefront"}
            pkg = {**pkg, "storefront": storefront}
        return pkg

    @mcp.tool(
        name="update_package",
        description="Update a package: toggle disabled, rename, or change price. Only provided fields are changed.",
        annotations=IDEMPOTENT,
    )
    @map_tebex_errors
    async def update_package(
        package_id: Annotated[int, Field(description="Package ID", ge=1)],
        disabled: Annotated[
            bool | None,
            Field(description="Set to true to disable the package on the webstore"),
        ] = None,
        name: Annotated[str | None, Field(description="New package name")] = None,
        price: Annotated[
            float | None, Field(description="New price in store currency", ge=0)
        ] = None,
    ) -> dict[str, Any]:
        await ctx.client.update_package(
            package_id, disabled=disabled, name=name, price=price
        )
        return ok(
            package_id=package_id,
            updated={"disabled": disabled, "name": name, "price": price},
        )
