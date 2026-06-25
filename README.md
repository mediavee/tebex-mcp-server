# tebex-mcp-server

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants operate a [Tebex](https://www.tebex.io) store via the [Plugin API](https://docs.tebex.io/developers/plugin-api/endpoints): packages, payments, gift cards, coupons, bans, sales, community goals, command queue, and player lookups — all behind one bearer-authenticated HTTP endpoint.

Built on **[FastMCP 3.x](https://gofastmcp.com)** + Python 3.12 + asyncio. The skeleton (settings → client → tool registration → custom routes) is the same one used by [`ptero-mcp-server`](../ptero-mcp-server) and is intentionally portable to other REST-backed integrations.

---

## Overview

The Tebex Plugin API is a clean REST surface but it's tedious to use from a chat assistant: 30+ endpoints, opaque pagination on `/payments`, scoped IDs (player vs Tebex player vs txn vs hashid), and a 500-req / 5-min rate limit that punishes naive scraping. This server wraps it as **typed MCP tools** with a few opinionated helpers:

- `search_payments` — paginates `/payments` automatically with **early-exit** on the date boundary (since payments are returned newest-first), filters by username substring, status, package id, and amount range, and reports `has_more` so the assistant can decide whether to keep digging.
- Path components are URL-quoted before hitting the API — no path-traversal shenanigans from a creative LLM prompt.
- A single long-lived `httpx.AsyncClient` with retry + exponential backoff on 5xx and network errors (3 attempts, 0.4s → 0.8s → 1.6s).
- Structured logging via `structlog`: every Tebex request is logged at `DEBUG`, every 4xx/5xx at `WARNING` with the response body, every retry at `WARNING` with attempt counter and backoff.

## Features

- **Information** — store metadata, currency, game type
- **Packages** — list categories, list/get packages, update price/name/disabled flag
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
| `list_packages` | All packages with id, name, price, type, category, sale info |
| `get_package` | Full package details (description, image, …) |
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

### Field selection

The Tebex Plugin API does not support server-side field selection, so read tools return the full upstream payload. Client-side filtering is intentionally not implemented — the wire cost upstream would not change, and the marginal context savings are not worth the schema-tracking complexity. If a specific tool's payload becomes a problem in practice, narrow it at the call site.

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

## Reusing this skeleton

Same template as `ptero-mcp-server`. To start a new MCP service from this layout:

1. Replace `client.py` with your upstream API wrapper (httpx async, retry-aware).
2. Add a tool module per logical domain in `tools/` and register it in `tools/__init__.py`.
3. Update `Settings` in `config.py` with the env vars you need; `pydantic-settings` validates them at startup.
4. Add custom HTTP routes in `server.py` next to `/healthz`.

Everything else — auth middleware, FastMCP lifespan, structured logging, Docker, healthcheck — is reusable as-is.

## Deployment notes

- **Security.** Tebex secrets travel in the `X-Tebex-Secret` header. The server does not log them and does not persist them. **TLS in front is non-negotiable** unless the listener is bound to loopback or a private network (Tailscale, WireGuard). `MCP_AUTH_TOKEN` gates access at the bearer layer. `.env` is in `.gitignore` — keep it that way.
- **Rate limit.** The Plugin API caps at 500 requests per 5-minute rolling window per secret. With multi-store usage that quota is naturally per-store. `search_payments` mitigates burn by stopping as soon as it crosses the date floor or hits its result cap, but a long unbounded scan can still exhaust the budget. The `tebex_tool_error` log line surfaces 429s explicitly.
- **One process for many stores.** A single instance handles any number of stores concurrently — secrets are scoped per-request via a `ContextVar`, no global state.
- **Graceful shutdown.** `SIGTERM` / `SIGINT` closes the httpx client and FastMCP session manager, then exits. Uvicorn's 10-second graceful-shutdown timeout forces exit if anything hangs.

## License

Private. © Mediavee.
