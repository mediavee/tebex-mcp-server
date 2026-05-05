"""Shared helpers for tool handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from fastmcp.exceptions import ToolError

from tebex_mcp.client import TebexError
from tebex_mcp.logging import get_logger

log = get_logger(__name__)


def map_tebex_errors[**P, R](
    fn: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    """Translate :class:`TebexError` into FastMCP-friendly errors.

    A 404 from Tebex usually means "this resource doesn't exist" and a 429
    means we hit the rate limit (500 req / 5 min). Surface both with clear
    messages instead of stack traces.
    """

    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await fn(*args, **kwargs)
        except TebexError as exc:
            log.warning(
                "tebex_tool_error",
                tool=fn.__name__,
                status=exc.status,
                body=exc.body,
            )
            if exc.status == 404:
                raise ToolError(f"Tebex resource not found (404): {exc}") from exc
            if exc.status == 429:
                raise ToolError(
                    "Tebex API rate limit exceeded (429). "
                    "Limit is 500 requests per 5-minute window."
                ) from exc
            raise ToolError(f"Tebex API error ({exc.status}): {exc}") from exc

    return wrapper


def ok(**fields: Any) -> dict[str, Any]:
    """Tiny helper to build the standard ``{ok: true, ...}`` payload."""
    return {"ok": True, **fields}


# ──────────────────────────── tool annotation presets ──────────────────────────
#
# MCP `tool.annotations` are hints clients (Claude Code/Desktop) use to colour
# tools in the UI and decide whether to prompt for confirmation before calling.
# All our tools talk to a remote Tebex API, hence ``openWorldHint=True`` on every
# preset. The remaining axes split tools into:
#   READ_ONLY    — pure read, idempotent, safe.
#   IDEMPOTENT   — write but re-running the same call yields the same state.
#   DESTRUCTIVE  — irreversible or hard to undo.
#   WRITE        — non-idempotent write (each call has a side effect, e.g.
#                  appending a note, creating a new resource).

READ_ONLY: dict[str, Any] = {
    "readOnlyHint": True,
    "idempotentHint": True,
    "openWorldHint": True,
}

IDEMPOTENT: dict[str, Any] = {
    "readOnlyHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

DESTRUCTIVE: dict[str, Any] = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": True,
}

WRITE: dict[str, Any] = {
    "readOnlyHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}
