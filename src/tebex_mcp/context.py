"""Shared dependencies wired into every tool handler."""

from __future__ import annotations

from dataclasses import dataclass

from tebex_mcp.client import TebexClient
from tebex_mcp.config import Settings


@dataclass(slots=True, frozen=True)
class ToolContext:
    settings: Settings
    client: TebexClient
