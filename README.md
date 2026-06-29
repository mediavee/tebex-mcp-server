# tebex-mcp-server

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants operate a [Tebex](https://www.tebex.io) store via the [Plugin API](https://docs.tebex.io/plugin): packages, payments, gift cards, coupons, bans, sales, community goals, command queue, and player lookups — plus read-only storefront views (package descriptions, pricing) via the Headless API — all behind one bearer-authenticated HTTP endpoint.

Built on **[FastMCP 3.x](https://gofastmcp.com)** + Python 3.13 + asyncio.

---

## Overview

The Tebex Plugin API is tedious from a chat assistant: 30+ endpoints, opaque `/payments` pagination, several distinct ID kinds, and a 500-req / 5-min rate limit. This server wraps it as **typed MCP tools** with a few helpers:

- `search_payments` — auto-paginates `/payments` with **early-exit** on the date boundary (payments are newest-first), filters by username, status, package, and amount, and reports `has_more`.
- Path components are URL-quoted before the call.
- One long-lived `httpx.AsyncClient` with retry + exponential backoff on 5xx/network errors.
- Structured `structlog` logging: every request at `DEBUG`, 4xx/5xx and retries at `WARNING`.

## Features

- **Information** — store metadata, currency, game type
- **Packages** — list categories, list/get packages (optional storefront description/pricing via the Headless API), update price/name/disabled flag
- **Payments** — list (paged or capped), search with multi-criteria filtering and early-exit pagination, get, create manual payments, update status, add notes
- **Checkout** — generate signed checkout URLs
- **Gift cards** — full CRUD plus topup, void, and customer-code lookup
- **Coupons** — full CRUD with all 14 Tebex options exposed as typed parameters
- **Bans** — list and create user/IP bans
- **Sales** — list active sales
- **Community goals** — list and inspect
- **Player lookup** — Ultimate-plan endpoint for username/UUID → bans, chargeback rate, payments, totals
- **Command queue** — due commands, offline commands, online commands, bulk delete
- **Bearer-authenticated HTTP transport**, structured JSON-capable logging, retry-aware HTTP client

## Quick start

### 1. Prerequisites

- One or more Tebex **Plugin API secret keys** (`Creator Panel → Game Servers → Secret Key`, one per store you want to manage)
- Python **3.12+** **or** Docker
- (Dev) [`uv`](https://github.com/astral-sh/uv) for dependency management

### 2. Configure environment

```bash
cp .env.example .env
```

Only `MCP_AUTH_TOKEN` is required server-side. Tebex secrets are **not** stored on the server — each MCP client passes its store's secret on every request via the `X-Tebex-Secret` header (see Multi-store usage below).

```env
MCP_AUTH_TOKEN=$(openssl rand -hex 32)
```

### 3. Run with Docker Compose

```bash
docker compose up -d --build
```

The server listens on `http://0.0.0.0:3000/mcp` by default. A `/healthz` endpoint is exposed for container health checks.

### 4. Connect Claude Code

One MCP entry per Tebex store, all pointing at the same server with a different `X-Tebex-Secret`:

```bash
claude mcp add tebex-storeFR --transport http http://localhost:3000/mcp \
  --header "Authorization: Bearer $MCP_AUTH_TOKEN" \
  --header "X-Tebex-Secret: $STORE_FR_SECRET"

claude mcp add tebex-storeEN --transport http http://localhost:3000/mcp \
  --header "Authorization: Bearer $MCP_AUTH_TOKEN" \
  --header "X-Tebex-Secret: $STORE_EN_SECRET"
```

For Claude Desktop or other clients that use JSON config:

```json
{
  "mcpServers": {
    "tebex-storeFR": {
      "type": "http",
      "url": "http://localhost:3000/mcp",
      "headers": {
        "Authorization": "Bearer <your bearer token>",
        "X-Tebex-Secret": "<your store FR secret>"
      }
    },
    "tebex-storeEN": {
      "type": "http",
      "url": "http://localhost:3000/mcp",
      "headers": {
        "Authorization": "Bearer <your bearer token>",
        "X-Tebex-Secret": "<your store EN secret>"
      }
    }
  }
}
```

Once connected, the skill file [`SKILL.md`](./SKILL.md) at the repo root is picked up automatically by clients that support it, giving the assistant concrete methodology for common flows (refund a payment, search a player's history, create a coupon, etc.).

## Multi-store usage

A single `tebex-mcp` instance serves any number of Tebex stores. The server holds **no Tebex secret in its config** — every `/mcp` request must include an `X-Tebex-Secret` header carrying the per-store Plugin API secret, and the server uses it for the upstream call to `https://plugin.tebex.io`.

- The secret lives in your MCP client config (Claude Code/Desktop), one entry per store.
- Concurrent requests from different MCP entries are isolated via a Python `ContextVar` set by the auth middleware — there is no global mutable state.
- A request without a valid `X-Tebex-Secret` is rejected with HTTP 400 before reaching FastMCP.
- Rate limits (500 req / 5 min) are naturally per-secret on Tebex's side, so isolating stores by secret also isolates their quotas.

To switch stores from Claude Code at runtime, use `claude mcp` to enable/disable the entry you want, or talk directly to the entry whose name matches the target store.

## Tools

Thirty-five MCP tools grouped into nine categories. See [`SKILL.md`](./SKILL.md) for composition patterns and methodology.

### Information

| Tool | Description |
|---|---|
| `get_store_info` | Store and server info: id, name, domain, currency, game type, online mode |

### Packages

| Tool | Description |
|---|---|
| `list_categories` | All categories with nested package summaries |
| `list_packages` | All packages: id, name, price, type, category, expiry, limits |
| `get_package` | Full package config (price, type, category, expiry, limits, GUI item); `include_description=true` adds the storefront view (description, tax-inclusive pricing, media) via the Headless API |
| `update_package` | Toggle disabled, rename, or change price |

### Payments

| Tool | Description |
|---|---|
| `search_payments` | Multi-criteria filter (username, date range, package, status, amount) with auto-pagination and early-exit on date boundary. Returns `has_more` |
| `list_payments` | Latest payments (cap at 100) |
| `list_payments_paged` | Standard 25-per-page paginated listing |
| `get_payment` | Full payment details by transaction id |
| `get_payment_fields` | Required `options` fields for `create_payment` on a given package |
| `create_payment` | Manual payment — assign packages to a player without checkout |
| `update_payment` | Change username or status (`complete` / `chargeback` / `refund`) |
| `add_payment_note` | Append a note to a payment |
| `create_checkout` | Generate a checkout URL for a player + package |

### Gift cards

`list_gift_cards`, `get_gift_card`, `lookup_gift_card`, `create_gift_card`, `topup_gift_card`, `void_gift_card`

### Coupons

`list_coupons`, `get_coupon`, `create_coupon`, `delete_coupon`

### Bans

`list_bans`, `create_ban`

### Sales

`list_sales`

### Community goals

`list_community_goals`, `get_community_goal`

### Players & command queue

`lookup_player`, `get_player_packages`, `get_command_queue`, `get_offline_commands`, `get_online_commands`, `delete_commands`

### Response shapes

Payment and player tools return **normalized** payloads (see `normalize.py`): amounts as floats, currency as ISO code, status lowercased, dates as ISO, null/empty fields dropped, and — for `lookup_player` — each payment's `tbx-…` `transaction_id` surfaced (the only endpoint that carries it). Payments follow a **lean-list / full-detail** split: `list_payments`, `search_payments` and `list_payments_paged` return lean rows (id, date, amount, currency, status, player id+name, package id+name) sized for scanning and stats, while `get_payment` returns the full record (email, gateway, uuid, quantity, notes) — roughly 40% fewer tokens on the listing path, the standard summary/detail pattern. Every other read tool passes the flat Tebex JSON straight through.

## Configuration

All configuration is via environment variables (loaded from process env, then `.env`).

| Variable         | Required | Default     | Description                                                            |
|------------------|----------|-------------|------------------------------------------------------------------------|
| `MCP_AUTH_TOKEN` | yes      | —           | Bearer token required by every MCP client. `openssl rand -hex 32`      |
| `HTTP_HOST`      | no       | `0.0.0.0`   | Bind host for the HTTP listener                                        |
| `HTTP_PORT`      | no       | `3000`      | Bind port                                                              |
| `LOG_LEVEL`      | no       | `INFO`      | Logger level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)                     |
| `LOG_JSON`       | no       | `false`     | Emit logs as JSON (recommended for production)                         |

The Tebex Plugin API secret is **not** an env var — it is supplied per-request by the MCP client through the `X-Tebex-Secret` header (see Multi-store usage above).

The included `docker-compose.yml` also honors a `HTTP_BIND` variable for the *host-side* of the port mapping — set it to a Tailscale IP or `127.0.0.1` to avoid exposing the server on public interfaces.

## Logging

Every Tebex API call is logged with structured fields:

| Event | Level | Fields |
|---|---|---|
| `tebex_request` | DEBUG | method, path, status |
| `tebex_request_failed` | WARNING | method, path, status, body |
| `tebex_request_server_error_retry` | WARNING | method, path, status, attempt, backoff_s |
| `tebex_request_network_retry` | WARNING | method, path, attempt, backoff_s, error |
| `tebex_request_network_error` | ERROR | method, path, attempt, error |
| `tebex_tool_error` | WARNING | tool, status, body |
| `tebex_mcp_started` / `tebex_mcp_shutting_down` / `tebex_mcp_listening` | INFO | version, host, port, urls |

Set `LOG_JSON=true` in production to feed the lines into your log aggregator without further parsing.

## Development

Use `uv` for the local toolchain:

```bash
uv sync                          # create .venv + install deps
uv run tebex-mcp                 # run the server
uv run python -m tebex_mcp       # equivalent
uv run ruff check src            # lint
uv run ruff format src           # format
uv run mypy src                  # type-check (strict)
```

The codebase is small, async-first, and flat:

```
src/tebex_mcp/
├── __main__.py        # python -m tebex_mcp / console script entry
├── server.py          # FastMCP app + lifespan + ASGI wiring + uvicorn
├── config.py          # pydantic-settings: typed env loading
├── logging.py         # structlog config (text or JSON)
├── auth.py            # Bearer token middleware (constant-time compare)
├── client.py          # httpx-based TebexClient (retry, backoff, URL-quoted paths)
├── normalize.py        # Map inconsistent Tebex payloads onto stable shapes
├── context.py         # Shared dependency container (ToolContext)
└── tools/
    ├── __init__.py    # register_all(mcp, ctx)
    ├── _common.py     # Shared error mapping + ok() helper
    ├── information.py
    ├── packages.py
    ├── payments.py    # includes search_payments with auto-pagination
    ├── gift_cards.py
    ├── coupons.py
    ├── bans.py
    ├── sales.py
    ├── community_goals.py
    ├── players.py
    └── command_queue.py
```

## Deployment notes

- **Security.** Tebex secrets travel in the `X-Tebex-Secret` header. The server does not log them and does not persist them. **TLS in front is non-negotiable** unless the listener is bound to loopback or a private network (Tailscale, WireGuard). `MCP_AUTH_TOKEN` gates access at the bearer layer. `.env` is in `.gitignore` — keep it that way.
- **Rate limit.** The Plugin API caps at 500 requests per 5-minute rolling window per secret. With multi-store usage that quota is naturally per-store. `search_payments` mitigates burn by stopping as soon as it crosses the date floor or hits its result cap, but a long unbounded scan can still exhaust the budget. The `tebex_tool_error` log line surfaces 429s explicitly.
- **One process for many stores.** A single instance handles any number of stores concurrently — secrets are scoped per-request via a `ContextVar`, no global state.
- **Graceful shutdown.** `SIGTERM` / `SIGINT` closes the httpx client and FastMCP session manager, then exits. Uvicorn's 10-second graceful-shutdown timeout forces exit if anything hangs.

## License

[MIT](./LICENSE) © Mediavee.
