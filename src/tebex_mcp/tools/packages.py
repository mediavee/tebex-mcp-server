"""Package tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import map_tebex_errors, ok


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="list_categories",
        description="List all categories with nested package summaries.",
    )
    @map_tebex_errors
    async def list_categories() -> Any:
        return await ctx.client.get_listing()

    @mcp.tool(
        name="list_packages",
        description="List all packages with id, name, price, type, category, and sale info.",
    )
    @map_tebex_errors
    async def list_packages() -> Any:
        return await ctx.client.list_packages()

    @mcp.tool(
        name="get_package",
        description="Get full package details: name, price, description, image, type, category.",
    )
    @map_tebex_errors
    async def get_package(
        package_id: Annotated[int, Field(description="Package ID", ge=1)],
    ) -> Any:
        return await ctx.client.get_package(package_id)

    @mcp.tool(
        name="update_package",
        description="Update a package: toggle disabled, rename, or change price. Only provided fields are changed.",
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
