"""Map raw Tebex Plugin API payloads onto stable, consistent shapes.

The Plugin API is inconsistent across endpoints: payment amounts are strings on
some routes and numbers on others; payment status is a capitalized string on
the payments routes but a numeric code in the player-lookup payload; the
`tbx-…` transaction id is exposed only by player lookup, never by the payment
listings. These helpers coerce everything onto one shape so tools — and the LLM
reading them — never have to special-case an endpoint.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

# Numeric status codes appear only in the player-lookup payload, and Tebex does
# not document them. 1=complete is verified (status-1 payments sum exactly to
# the reported purchase totals); 2/3 are inferred from the canonical
# {Complete, Refund, Chargeback} string set. `status_code` is always preserved,
# so the raw value is never lost when a code is unmapped.
_PLAYER_PAYMENT_STATUS = {1: "complete", 2: "refund", 3: "chargeback"}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _status(value: Any) -> str | None:
    return value.lower() if isinstance(value, str) and value else None


def _currency(raw: Any) -> str | None:
    if isinstance(raw, dict):
        return raw.get("iso_4217")
    return raw if isinstance(raw, str) else None


def _player(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {"id": raw.get("id"), "name": raw.get("name"), "uuid": raw.get("uuid")}


def _packages(raw: Any) -> list[dict[str, Any]]:
    items = raw if isinstance(raw, list) else []
    return [
        {"id": p.get("id"), "name": p.get("name"), "quantity": p.get("quantity")}
        for p in items
        if isinstance(p, dict)
    ]


def _epoch_to_iso(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _compact(value: Any) -> Any:
    """Drop null/empty (None, "", [], {}) entries recursively to save tokens.

    Falsy-but-meaningful values (0, 0.0, False) are kept.
    """
    if isinstance(value, dict):
        return {k: _compact(v) for k, v in value.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [_compact(v) for v in value]
    return value


def payment(raw: dict[str, Any]) -> dict[str, Any]:
    """Full payment detail from /payments/{txn}. Use payment_summary for lists.

    These routes expose only the numeric `id`, never the `tbx-…` transaction id
    that get/update/note require — that one comes from `lookup_player`.
    """
    gateway = raw.get("gateway")
    return _compact(
        {
            "id": raw.get("id"),
            "amount": _to_float(raw.get("amount")),
            "currency": _currency(raw.get("currency")),
            "status": _status(raw.get("status")),
            "date": raw.get("date"),
            "email": raw.get("email"),
            "gateway": gateway.get("name") if isinstance(gateway, dict) else gateway,
            "player": _player(raw.get("player")),
            "packages": _packages(raw.get("packages")),
            "notes": raw.get("notes"),
            "creator_code": raw.get("creator_code"),
        }
    )


def payment_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Lean payment for listings: just what stats and scanning need. Call
    get_payment for the full record (email, gateway, notes, uuid, quantity)."""
    player = raw.get("player")
    packages = raw.get("packages") if isinstance(raw.get("packages"), list) else []
    return _compact(
        {
            "id": raw.get("id"),
            "date": raw.get("date"),
            "amount": _to_float(raw.get("amount")),
            "currency": _currency(raw.get("currency")),
            "status": _status(raw.get("status")),
            "player": {"id": player.get("id"), "name": player.get("name")}
            if isinstance(player, dict)
            else None,
            "packages": [
                {"id": p.get("id"), "name": p.get("name")}
                for p in packages
                if isinstance(p, dict)
            ],
        }
    )


def pagination(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize the flat Laravel paginator returned by /payments?paged=1."""
    out = {
        "current_page": raw.get("current_page"),
        "last_page": raw.get("last_page"),
        "total": raw.get("total"),
    }
    if raw.get("per_page") is not None:
        out["per_page"] = raw["per_page"]
    return out


def paged_payments(raw: dict[str, Any]) -> dict[str, Any]:
    data = raw.get("data") or []
    return {
        "data": [payment_summary(p) for p in data if isinstance(p, dict)],
        "pagination": pagination(raw),
    }


def _player_payment(raw: dict[str, Any]) -> dict[str, Any]:
    code = raw.get("status")
    return _compact(
        {
            "transaction_id": raw.get("txn_id"),
            "date": _epoch_to_iso(raw.get("time")),
            "amount": _to_float(raw.get("price")),
            "currency": raw.get("currency"),
            "status_code": code,
            "status": _PLAYER_PAYMENT_STATUS.get(code) if isinstance(code, int) else None,
        }
    )


def player_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize /user/{id}. Exposes each payment's `tbx-…` transaction_id and
    maps `player.id` to the integer id that other player tools expect."""
    player_raw = raw.get("player") or {}
    avatar = None
    meta = player_raw.get("meta")
    if isinstance(meta, str):
        try:
            avatar = json.loads(meta).get("avatar")
        except (ValueError, AttributeError):
            avatar = None
    payments = raw.get("payments") or []
    return _compact(
        {
            "player": {
                "id": player_raw.get("plugin_username_id"),
                "uuid": player_raw.get("id"),
                "username": player_raw.get("username"),
                "avatar": avatar,
            },
            "ban_count": raw.get("banCount"),
            "chargeback_rate": raw.get("chargebackRate"),
            "purchase_totals": raw.get("purchaseTotals") or {},
            "payments": [_player_payment(p) for p in payments if isinstance(p, dict)],
        }
    )
