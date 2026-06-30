# tebex-mcp-server

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants operate a [Tebex](https://www.tebex.io) store via the [Plugin API](https://docs.tebex.io/plugin): packages, payments, gift cards, coupons, bans, sales, community goals, command queue, and player lookups — plus read-only storefront views (descriptions, pricing) via the Headless API, all behind one bearer-authenticated HTTP endpoint.

## Overview

The Tebex Plugin API is awkward from a chat assistant: 30+ endpoints, opaque `/payments` pagination, several distinct ID kinds, and a 500-req / 5-min rate limit. This server wraps it as typed MCP tools over one long-lived, retry-aware HTTP client, and adds `search_payments` — which auto-paginates and early-exits on the date boundary (payments are newest-first) so multi-criteria searches don't burn the whole quota. Payment and player payloads are normalized onto stable shapes (see [Response shapes](#response-shapes)).

Methodology and composition patterns for the assistant live in [`SKILL.md`](./SKILL.md), picked up automatically by clients that support skills.

## Features

- **Information** — store metadata, currency, game type.
- **Packages** — list categories, list/get packages (optional storefront description/pricing via the Headless API), update price/name/disabled flag.
- **Payments** — list (paged or capped), multi-criteria search with early-exit pagination, get, create manual payments, update status, add notes, signed checkout URLs.
- **Gift cards** — full CRUD plus topup, void, and customer-code lookup.
- **Coupons** — full CRUD with all Tebex options as typed parameters.
- **Bans** — list and create user / IP bans.
- **Sales** / **community goals** — list and inspect.
- **Player lookup** — Ultimate-plan endpoint: username/UUID → bans, chargeback rate, payments, totals.
- **Command queue** — due, offline, and online commands; bulk delete.
- Multi-tenant: per-request store secret via header, bearer-gated, isolated per store.
- Structured logging, `/healthz`, Docker-ready.

## Quick start

### 1. Prerequisites

- One or more Tebex **Plugin API secret keys** (`Creator Panel → Game Servers → Secret Key`, one per store)
- Docker + Docker Compose (or Python ≥ 3.13 and [`uv`](https://github.com/astral-sh/uv) for local runs)

### 2. Configure environment

```bash
cp .env.example .env
# set MCP_AUTH_TOKEN (openssl rand -hex 32); tune HTTP_HOST / HTTP_PORT / LOG_*
```

Tebex secrets are **not** in `.env` — clients send their store's secret per request (step 4).

### 3. Run with Docker Compose

```bash
docker compose up -d --build
curl http://127.0.0.1:3000/healthz   # {"status":"ok",...}
```

The server listens on `http://0.0.0.0:3000/mcp` by default.

### 4. Connect Claude Code

One MCP entry per Tebex store, all pointing at the same server with a different `X-Tebex-Secret`:

```bash
claude mcp add tebex-storeFR --transport http http://localhost:3000/mcp \
  --header "Authorization: Bearer $MCP_AUTH_TOKEN" \
  --header "X-Tebex-Secret: $STORE_FR_SECRET"
```

For Claude Desktop or other JSON-config clients:

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
    }
  }
}
```

## Multi-store usage

A single instance serves any number of Tebex stores. The server holds **no Tebex secret** — every `/mcp` request must carry an `X-Tebex-Secret` header (plus the shared `Authorization: Bearer`), used for the upstream call to `https://plugin.tebex.io`. Concurrent requests are isolated via a `ContextVar` set by the auth middleware; there is no global mutable state. A request without a secret is rejected with HTTP 400. The 500-req / 5-min rate limit is per-secret on Tebex's side, so isolating stores by secret also isolates their quotas.

## Tools

Grouped by domain. See [`SKILL.md`](./SKILL.md) for composition patterns and methodology.

### Information

| Tool | Description |
|---|---|
| `get_store_info` | Store and server info: id, name, domain, currency, game type, online mode |

### Packages

| Tool | Description |
|---|---|
| `list_categories` | All categories with nested package summaries |
| `list_packages` | All packages: id, name, price, type, category, expiry, limits |
| `get_package` | Full package config; `include_description=true` adds the storefront view (description, tax-inclusive pricing, media) via the Headless API |
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

### Bans / sales / community goals

`list_bans`, `create_ban`, `list_sales`, `list_community_goals`, `get_community_goal`

### Players & command queue

`lookup_player`, `get_player_packages`, `get_command_queue`, `get_offline_commands`, `get_online_commands`, `delete_commands`

### Response shapes

Payment and player tools return **normalized** payloads (see `normalize.py`): amounts as floats, currency as ISO code, status lowercased, dates as ISO, null/empty fields dropped. Payments use a lean-list / full-detail split — listings return scannable rows, `get_payment` returns the full record — for ~40% fewer tokens on the listing path. Every other read tool passes the flat Tebex JSON straight through.

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `MCP_AUTH_TOKEN` | yes | — | Bearer token required on every request. Generate with `openssl rand -hex 32` |
| `HTTP_HOST` | no | `0.0.0.0` | Bind host |
| `HTTP_PORT` | no | `3000` | Bind port |
| `LOG_LEVEL` | no | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LOG_JSON` | no | `false` | Emit logs as JSON (recommended in production) |

The Tebex Plugin API secret is supplied per request via the `X-Tebex-Secret` header, never as an env var. The `docker-compose.yml` also honors `HTTP_BIND` for the host side of the port mapping — set it to a Tailscale IP or `127.0.0.1` to avoid public exposure.

## Logging

`structlog`; human-readable by default, JSON via `LOG_JSON=true`. Every Tebex call logs method / path / status (`DEBUG`), with 4xx/5xx, retries, and 429s surfaced at `WARNING`. Store secrets are never logged.

## Development

```bash
uv sync
uv run tebex-mcp                 # run the server
uv run ruff check src            # lint
uv run mypy src                  # type-check (strict)
```

## Deployment notes

- **Published image.** Tagging a release (`git tag v1.2.3 && git push --tags`) builds and pushes `ghcr.io/mediavee/tebex-mcp-server:1.2.3` + `:latest`. To run from the registry, uncomment the `image:` line in `docker-compose.yml`, then `docker compose pull && docker compose up -d`.
- **Security.** Store secrets travel in the `X-Tebex-Secret` header; never logged or persisted. TLS in front is mandatory unless bound to loopback / Tailscale / WireGuard. `MCP_AUTH_TOKEN` gates access. Keep `.env` git-ignored.
- **Rate limit.** The Plugin API caps at 500 requests per 5-minute rolling window per secret. `search_payments` mitigates burn by stopping at the date floor or result cap, but a long unbounded scan can still exhaust it.
- **Graceful shutdown.** `SIGTERM` / `SIGINT` closes the HTTP client and FastMCP session manager, then exits (10s uvicorn cap).

## License

[MIT](./LICENSE) © Mediavee.
