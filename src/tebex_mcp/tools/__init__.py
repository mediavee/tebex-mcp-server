"""Tool registration entry point."""

from __future__ import annotations

from fastmcp import FastMCP

from tebex_mcp.context import ToolContext
from tebex_mcp.tools.bans import register as register_bans
from tebex_mcp.tools.command_queue import register as register_command_queue
from tebex_mcp.tools.community_goals import register as register_community_goals
from tebex_mcp.tools.coupons import register as register_coupons
from tebex_mcp.tools.gift_cards import register as register_gift_cards
from tebex_mcp.tools.information import register as register_information
from tebex_mcp.tools.packages import register as register_packages
from tebex_mcp.tools.payments import register as register_payments
from tebex_mcp.tools.players import register as register_players
from tebex_mcp.tools.recurring_payments import register as register_recurring_payments
from tebex_mcp.tools.sales import register as register_sales


def register_all(mcp: FastMCP, ctx: ToolContext) -> None:
    register_information(mcp, ctx)
    register_packages(mcp, ctx)
    register_payments(mcp, ctx)
    register_recurring_payments(mcp, ctx)
    register_gift_cards(mcp, ctx)
    register_coupons(mcp, ctx)
    register_bans(mcp, ctx)
    register_sales(mcp, ctx)
    register_community_goals(mcp, ctx)
    register_players(mcp, ctx)
    register_command_queue(mcp, ctx)
