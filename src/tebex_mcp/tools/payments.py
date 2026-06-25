"""Payment tools, including a paginating search."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from tebex_mcp import normalize
from tebex_mcp.client import PaymentStatus
from tebex_mcp.context import ToolContext
from tebex_mcp.tools._common import (
    DESTRUCTIVE,
    READ_ONLY,
    WRITE,
    map_tebex_errors,
    ok,
)


def _parse_user_iso(value: str, field: str) -> datetime:
    """Parse a user-supplied ISO-8601 date. Raises ToolError on malformed input."""
    parsed = _try_parse_iso(value)
    if parsed is None:
        raise ToolError(
            f"Invalid '{field}' date format. Use ISO 8601 (e.g. 2026-04-01)."
        )
    return parsed


def _try_parse_iso(value: str | None) -> datetime | None:
    """Best-effort ISO-8601 parse for upstream payment dates. Returns None on failure."""
    if not value:
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    @mcp.tool(
        name="search_payments",
        description=(
            "Filter payments by username, date range, package, status, amount; "
            "auto-paginates (early-exit on date). Results carry a numeric `id`, not a "
            "`tbx-…` id — use lookup_player to act on one (get/update_payment)."
        ),
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def search_payments(
        username: Annotated[
            str | None,
            Field(description="Player username (case-insensitive substring)"),
        ] = None,
        from_: Annotated[
            str | None,
            Field(alias="from", description="On/after this ISO date (e.g. 2026-04-01)"),
        ] = None,
        to: Annotated[
            str | None,
            Field(description="On/before this ISO date (e.g. 2026-04-14)"),
        ] = None,
        package_id: Annotated[int | None, Field(description="Package ID", ge=1)] = None,
        status: Annotated[
            PaymentStatus | None, Field(description="Payment status")
        ] = None,
        min_amount: Annotated[float | None, Field(description="Min amount")] = None,
        max_amount: Annotated[float | None, Field(description="Max amount")] = None,
        limit: Annotated[
            int | None, Field(description="Max results (default 25)", ge=1, le=100)
        ] = None,
        max_pages: Annotated[
            int | None,
            Field(description="Max pages to scan (default 20, 25/page)", ge=1, le=50),
        ] = None,
    ) -> dict[str, Any]:
        max_results = limit or 25
        max_scan = max_pages or 20

        from_dt = _parse_user_iso(from_, "from") if from_ else None
        to_dt = _parse_user_iso(to, "to") if to else None
        # Inclusive end-of-day to match the TS behavior.
        if to_dt is not None:
            to_dt = to_dt.replace(hour=23, minute=59, second=59, microsecond=999_000)

        username_lower = username.lower() if username else None
        results: list[dict[str, Any]] = []
        scanned = 0
        pages_scanned = 0
        hit_date_boundary = False
        reached_end = False

        for page in range(1, max_scan + 1):
            response = await ctx.client.list_payments_paged(page)
            pages_scanned += 1

            data = response.get("data") or []
            if not data:
                reached_end = True
                break

            for raw in data:
                scanned += 1
                item = normalize.payment_summary(raw)
                payment_date = _try_parse_iso(item.get("date"))

                # Payments are sorted desc — once we cross the lower bound, stop.
                # Skip date filtering on payments with unparseable dates rather
                # than aborting the whole search on one malformed entry.
                if payment_date is not None:
                    if from_dt is not None and payment_date < from_dt:
                        hit_date_boundary = True
                        break
                    if to_dt is not None and payment_date > to_dt:
                        continue
                elif from_dt is not None or to_dt is not None:
                    continue

                player_name = (item.get("player") or {}).get("name") or ""
                if username_lower and username_lower not in player_name.lower():
                    continue

                if status and item.get("status") != status:
                    continue

                if package_id is not None:
                    pkgs = item.get("packages") or []
                    if not any(p.get("id") == package_id for p in pkgs):
                        continue

                amount = item.get("amount") or 0.0
                if min_amount is not None and amount < min_amount:
                    continue
                if max_amount is not None and amount > max_amount:
                    continue

                results.append(item)
                if len(results) >= max_results:
                    break

            if hit_date_boundary or len(results) >= max_results:
                break

            last_page = response.get("last_page")
            if last_page is not None and page >= last_page:
                reached_end = True
                break

        has_more = not hit_date_boundary and not reached_end and len(results) >= max_results

        return {
            "results": results,
            "meta": {
                "matched": len(results),
                "scanned": scanned,
                "pages_scanned": pages_scanned,
                "has_more": has_more,
            },
        }

    @mcp.tool(
        name="list_payments",
        description=(
            "Latest payments (≤100), lean (id, date, amount, currency, status, "
            "player, packages). get_payment for full detail."
        ),
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def list_payments(
        limit: Annotated[
            int | None,
            Field(description="Max number of payments to return (default: 100)", ge=1, le=100),
        ] = None,
    ) -> list[dict[str, Any]]:
        raw = await ctx.client.list_payments(limit)
        return [normalize.payment_summary(p) for p in raw if isinstance(p, dict)]

    @mcp.tool(
        name="list_payments_paged",
        description="Get payments with pagination (25 per page). Returns {data, pagination}.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def list_payments_paged(
        page: Annotated[
            int | None, Field(description="Page number (1-indexed, default: 1)", ge=1)
        ] = None,
    ) -> dict[str, Any]:
        return normalize.paged_payments(await ctx.client.list_payments_paged(page))

    @mcp.tool(
        name="get_payment",
        description=(
            "Full payment detail by `tbx-…` transaction id (from lookup_player or a "
            "webhook/email; the listings' numeric id is rejected here)."
        ),
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_payment(
        transaction_id: Annotated[
            str, Field(description="`tbx-…` transaction id")
        ],
    ) -> dict[str, Any]:
        return normalize.payment(await ctx.client.get_payment(transaction_id))

    @mcp.tool(
        name="get_payment_fields",
        description="Get required `options` fields for create_payment on a given package.",
        annotations=READ_ONLY,
    )
    @map_tebex_errors
    async def get_payment_fields(
        package_id: Annotated[int, Field(description="Package ID", ge=1)],
    ) -> Any:
        return await ctx.client.get_payment_fields(package_id)

    @mcp.tool(
        name="create_payment",
        description="Create a manual payment — assign packages to a player without checkout.",
        annotations=WRITE,
    )
    @map_tebex_errors
    async def create_payment(
        ign: Annotated[
            str, Field(description="Player username (in-game name) receiving the packages")
        ],
        packages: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Packages to assign, each {id, options:{...}}. "
                    "Use get_payment_fields for option keys."
                ),
                min_length=1,
            ),
        ],
        price: Annotated[float, Field(description="Total price", ge=0)],
        note: Annotated[str, Field(description="Internal note")],
    ) -> dict[str, Any]:
        await ctx.client.create_payment(
            ign=ign, packages=packages, price=price, note=note
        )
        return ok(ign=ign, packages_count=len(packages))

    @mcp.tool(
        name="update_payment",
        description=(
            "Update a payment's username or status by `tbx-…` transaction id. "
            "'refund'/'chargeback' revokes packages and is effectively irreversible "
            "— confirm first."
        ),
        annotations=DESTRUCTIVE,
    )
    @map_tebex_errors
    async def update_payment(
        transaction_id: Annotated[
            str, Field(description="`tbx-…` id (via lookup_player or webhook)")
        ],
        username: Annotated[str | None, Field(description="New username")] = None,
        status: Annotated[
            Literal["complete", "chargeback", "refund"] | None,
            Field(description="New payment status"),
        ] = None,
    ) -> dict[str, Any]:
        await ctx.client.update_payment(
            transaction_id, username=username, status=status
        )
        return ok(
            transaction_id=transaction_id,
            updated={"username": username, "status": status},
        )

    @mcp.tool(
        name="add_payment_note",
        description="Add a note to a payment by `tbx-…` transaction id.",
        annotations=WRITE,
    )
    @map_tebex_errors
    async def add_payment_note(
        transaction_id: Annotated[
            str, Field(description="`tbx-…` id (via lookup_player or webhook)")
        ],
        note: Annotated[str, Field(description="Note text to add")],
    ) -> Any:
        return await ctx.client.add_payment_note(transaction_id, note)

    @mcp.tool(
        name="create_checkout",
        description="Generate a checkout URL for a player and package. Returns URL and expiration.",
        annotations=WRITE,
    )
    @map_tebex_errors
    async def create_checkout(
        package_id: Annotated[int, Field(description="Package ID", ge=1)],
        username: Annotated[str, Field(description="Player username")],
    ) -> Any:
        return await ctx.client.create_checkout(package_id, username)
