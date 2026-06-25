"""Async wrapper around the Tebex Plugin API.

Only methods used by the MCP tools are implemented. Auth is the per-server
secret key sent in the ``X-Tebex-Secret`` header.

Rate limit: 500 requests per 5-minute rolling window.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any, Literal
from urllib.parse import quote

import httpx

from tebex_mcp.config import Settings
from tebex_mcp.logging import get_logger

log = get_logger(__name__)


# Set per-request by the HTTP middleware from the ``X-Tebex-Secret`` header.
# Read inside ``_request`` so a single TebexClient instance can serve any
# number of stores without leaking secrets across concurrent requests.
current_secret: ContextVar[str | None] = ContextVar("tebex_secret", default=None)


class MissingSecretError(RuntimeError):
    """Raised when a tool runs without an X-Tebex-Secret in the request context."""


PaymentStatus = Literal["complete", "chargeback", "refund"]


def _q(value: str) -> str:
    """URL-quote a path component (no slashes survive)."""
    return quote(value, safe="")


class TebexError(Exception):
    """Wraps a non-2xx response from the Tebex API."""

    def __init__(self, message: str, status: int, body: object) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class TebexClient:
    """Thin async wrapper over the Tebex Plugin API (https://plugin.tebex.io)."""

    BASE_URL = "https://plugin.tebex.io"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Accept": "application/json"},
            timeout=httpx.Timeout(30.0, connect=10.0),
            transport=httpx.AsyncHTTPTransport(retries=2),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ──────────────────────────── core request ────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: Any | None = None,
        retries: int = 3,
    ) -> Any:
        params = {k: v for k, v in (query or {}).items() if v is not None}

        secret = current_secret.get()
        if not secret:
            raise MissingSecretError(
                "No Tebex secret in request context — the HTTP middleware should "
                "have rejected this request earlier."
            )
        request_headers = {"X-Tebex-Secret": secret}

        last_exc: Exception | None = None
        backoff = 0.4
        for attempt in range(retries):
            try:
                resp = await self._http.request(
                    method, path, params=params, json=body, headers=request_headers
                )
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == retries - 1:
                    log.error(
                        "tebex_request_network_error",
                        method=method,
                        path=path,
                        attempt=attempt + 1,
                        error=str(exc),
                    )
                    raise TebexError(
                        f"Tebex API {method} {path} network error: {exc}", 0, None
                    ) from exc
                log.warning(
                    "tebex_request_network_retry",
                    method=method,
                    path=path,
                    attempt=attempt + 1,
                    backoff_s=backoff,
                    error=str(exc),
                )
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code >= 500 and attempt < retries - 1:
                log.warning(
                    "tebex_request_server_error_retry",
                    method=method,
                    path=path,
                    status=resp.status_code,
                    attempt=attempt + 1,
                    backoff_s=backoff,
                )
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code == 204:
                log.debug("tebex_request", method=method, path=path, status=204)
                return None

            parsed: Any
            text = resp.text
            if text:
                try:
                    parsed = resp.json()
                except ValueError:
                    parsed = text
            else:
                parsed = None

            if not resp.is_success:
                log.warning(
                    "tebex_request_failed",
                    method=method,
                    path=path,
                    status=resp.status_code,
                    body=parsed,
                )
                raise TebexError(
                    f"Tebex API {method} {path} failed: "
                    f"{resp.status_code} {resp.reason_phrase}",
                    resp.status_code,
                    parsed,
                )

            log.debug("tebex_request", method=method, path=path, status=resp.status_code)
            return parsed

        raise TebexError(
            f"Tebex API {method} {path} exhausted retries", 0, None
        ) from last_exc

    # ───────────────────────────── information ─────────────────────────────

    async def get_information(self) -> Any:
        return await self._request("GET", "/information")

    # ──────────────────────────── command queue ────────────────────────────

    async def get_command_queue(self) -> Any:
        return await self._request("GET", "/queue")

    async def get_offline_commands(self) -> Any:
        return await self._request("GET", "/queue/offline-commands")

    async def get_online_commands(self, player_id: int) -> Any:
        return await self._request("GET", f"/queue/online-commands/{player_id}")

    async def delete_commands(self, ids: list[int]) -> None:
        await self._request("DELETE", "/queue", body={"ids": ids})

    # ─────────────────────────────── listing ───────────────────────────────

    async def get_listing(self) -> Any:
        return await self._request("GET", "/listing")

    # ────────────────────────────── packages ───────────────────────────────

    async def list_packages(self) -> Any:
        return await self._request("GET", "/packages")

    async def get_package(self, package_id: int) -> Any:
        return await self._request("GET", f"/package/{package_id}")

    async def update_package(
        self,
        package_id: int,
        *,
        disabled: bool | None = None,
        name: str | None = None,
        price: float | None = None,
    ) -> None:
        body = {"disabled": disabled, "name": name, "price": price}
        await self._request(
            "PUT",
            f"/package/{package_id}",
            body={k: v for k, v in body.items() if v is not None},
        )

    # ───────────────────────────── community goals ─────────────────────────

    async def list_community_goals(self) -> Any:
        return await self._request("GET", "/community_goals")

    async def get_community_goal(self, goal_id: int) -> Any:
        return await self._request("GET", f"/community_goals/{goal_id}")

    # ─────────────────────────────── payments ──────────────────────────────

    async def list_payments(self, limit: int | None = None) -> Any:
        return await self._request("GET", "/payments", query={"limit": limit})

    async def list_payments_paged(self, page: int | None = None) -> dict[str, Any]:
        return await self._request(
            "GET", "/payments", query={"paged": 1, "page": page or 1}
        )

    async def get_payment(self, transaction_id: str) -> Any:
        return await self._request("GET", f"/payments/{_q(transaction_id)}")

    async def get_payment_fields(self, package_id: int) -> Any:
        return await self._request("GET", f"/payments/fields/{package_id}")

    async def create_payment(
        self,
        *,
        ign: str,
        packages: list[dict[str, Any]],
        price: float,
        note: str,
    ) -> None:
        await self._request(
            "POST",
            "/payments",
            body={"ign": ign, "packages": packages, "price": price, "note": note},
        )

    async def update_payment(
        self,
        transaction_id: str,
        *,
        username: str | None = None,
        status: PaymentStatus | None = None,
    ) -> None:
        body = {"username": username, "status": status}
        await self._request(
            "PUT",
            f"/payments/{_q(transaction_id)}",
            body={k: v for k, v in body.items() if v is not None},
        )

    async def add_payment_note(self, transaction_id: str, note: str) -> Any:
        return await self._request(
            "POST", f"/payments/{_q(transaction_id)}/note", body={"note": note}
        )

    # ─────────────────────────────── checkout ──────────────────────────────

    async def create_checkout(self, package_id: int, username: str) -> Any:
        return await self._request(
            "POST", "/checkout", body={"package_id": package_id, "username": username}
        )

    # ────────────────────────────── gift cards ─────────────────────────────

    async def list_gift_cards(self) -> Any:
        return await self._request("GET", "/gift-cards")

    async def get_gift_card(self, gift_card_id: int) -> Any:
        return await self._request("GET", f"/gift-cards/{gift_card_id}")

    async def lookup_gift_card(self, code: str) -> Any:
        return await self._request("GET", f"/gift-cards/lookup/{_q(code)}")

    async def create_gift_card(
        self, *, expires_at: str, note: str, amount: float
    ) -> Any:
        return await self._request(
            "POST",
            "/gift-cards",
            body={"expires_at": expires_at, "note": note, "amount": amount},
        )

    async def topup_gift_card(self, gift_card_id: int, amount: float) -> Any:
        return await self._request(
            "PUT", f"/gift-cards/{gift_card_id}", body={"amount": amount}
        )

    async def void_gift_card(self, gift_card_id: int) -> None:
        await self._request("DELETE", f"/gift-cards/{gift_card_id}")

    # ─────────────────────────────── coupons ───────────────────────────────

    async def list_coupons(self, page: int | None = None) -> Any:
        return await self._request("GET", "/coupons", query={"page": page})

    async def get_coupon(self, coupon_id: int) -> Any:
        return await self._request("GET", f"/coupons/{coupon_id}")

    async def create_coupon(self, payload: dict[str, Any]) -> Any:
        return await self._request(
            "POST",
            "/coupons",
            body={k: v for k, v in payload.items() if v is not None},
        )

    async def delete_coupon(self, coupon_id: int) -> None:
        await self._request("DELETE", f"/coupons/{coupon_id}")

    # ──────────────────────────────── bans ─────────────────────────────────

    async def list_bans(self) -> Any:
        return await self._request("GET", "/bans")

    async def create_ban(
        self, *, reason: str, ip: str | None = None, user: str | None = None
    ) -> Any:
        body = {"reason": reason, "ip": ip, "user": user}
        return await self._request(
            "POST", "/bans", body={k: v for k, v in body.items() if v is not None}
        )

    # ──────────────────────────────── sales ────────────────────────────────

    async def list_sales(self) -> Any:
        return await self._request("GET", "/sales")

    # ─────────────────────────────── players ───────────────────────────────

    async def lookup_player(self, identifier: str) -> Any:
        return await self._request("GET", f"/user/{_q(identifier)}")

    async def get_player_packages(
        self, player_id: int, package_id: int | None = None
    ) -> Any:
        return await self._request(
            "GET",
            f"/player/{player_id}/packages",
            query={"package": package_id},
        )
