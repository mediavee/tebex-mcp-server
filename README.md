# tebex-mcp-server

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants operate a [Tebex](https://www.tebex.io) store via the [Plugin API](https://docs.tebex.io/developers/plugin-api/endpoints): packages, payments, gift cards, coupons, bans, sales, community goals, command queue, and player lookups.

Built on **[FastMCP 3.x](https://gofastmcp.com)** + Python 3.12 + asyncio. Single-tenant stdio transport — one process serves one Tebex store.

---

## Overview

The Tebex Plugin API is a clean REST surface but it's tedious to use from a chat assistant: 30+ endpoints, opaque pagination on `/payments`, scoped IDs (player vs Tebex player vs txn vs hashid), and a 500-req / 5-min rate limit that punishes naive scraping. This server wraps it as **typed MCP tools** with a few opinionated helpers:

- `search_payments` — paginates `/payments` automatically with **early-exit** on the date boundary (since payments are returned newest-first), filters by username substring, status, package id, and amount range, and reports `has_more` so the assistant can decide whether to keep digging.
- Path components are URL-quoted before hitting the API — no path-traversal shenanigans from a creative LLM prompt.
- A single long-lived `httpx.AsyncClient` with retry + exponential backoff on 5xx and network errors (3 attempts, 0.4s → 0.8s → 1.6s).
- Structured logging via `structlog` on stderr (stdout is reserved for the MCP JSON-RPC stream).

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
- **Recurring payments** — list, get, cancel/pause/reactivate subscriptions

## Quick start

### 1. Prerequisites

- A Tebex **Plugin API secret key** (`Creator Panel → Game Servers → Secret Key`)
- Python **3.12+** with [`uv`](https://github.com/astral-sh/uv) — recommended

### 2. Install

```bash
uv sync
```

Or, for transient use straight from the repo:

```bash
uv run --from . tebex-mcp
```

### 3. Connect Claude Code / Claude Desktop

Each MCP client entry spawns its own subprocess with the store's secret in its environment. Run **one entry per store** you want to manage.

**Claude Code** (`~/.config/claude/claude_desktop_config.json` or via `claude mcp add`):

```bash
claude mcp add tebex-storeFR -- env TEBEX_SECRET=$STORE_FR_SECRET tebex-mcp
claude mcp add tebex-storeEN -- env TEBEX_SECRET=$STORE_EN_SECRET tebex-mcp
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "tebex-storeFR": {
      "command": "tebex-mcp",
      "env": {
        "TEBEX_SECRET": "<your store FR secret>"
      }
    },
    "tebex-storeEN": {
      "command": "tebex-mcp",
      "env": {
        "TEBEX_SECRET": "<your store EN secret>"
      }
    }
  }
}
```

If `tebex-mcp` is not on the client's `PATH`, point at the absolute uv-managed binary or use `uvx --from <repo-path> tebex-mcp` as the `command`.

Once connected, the skill file [`SKILL.md`](./SKILL.md) at the repo root is picked up automatically by clients that support it, giving the assistant concrete methodology for common flows (refund a payment, search a player's history, create a coupon, etc.).

## Tools

Thirty-one MCP tools grouped into ten categories. See [`SKILL.md`](./SKILL.md) for composition patterns and methodology.

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

### Recurring payments (subscriptions)

`list_recurring_payments`, `get_recurring_payment`, `cancel_recurring_payment`, `pause_recurring_payment` (1-12 months), `reactivate_recurring_payment`

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

| Variable        | Required | Default | Description                                                |
|-----------------|----------|---------|------------------------------------------------------------|
| `TEBEX_SECRET`  | yes      | —       | Plugin API secret of the store this instance manages       |
| `LOG_LEVEL`     | no       | `INFO`  | Logger level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)         |
| `LOG_JSON`      | no       | `false` | Emit logs as JSON (recommended for production aggregation) |

Logs go to **stderr**. stdout is reserved for the MCP JSON-RPC stream.

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
| `tebex_mcp_started` / `tebex_mcp_shutting_down` | INFO | version |

Set `LOG_JSON=true` in production to feed the lines into your log aggregator without further parsing.

## Development

```bash
uv sync                          # create .venv + install deps
uv run tebex-mcp                 # run the server (reads .env)
uv run python -m tebex_mcp       # equivalent
uv run ruff check src            # lint
uv run ruff format src           # format
```

The codebase is small, async-first, and flat:

```
src/tebex_mcp/
├── __main__.py        # python -m tebex_mcp / console script entry
├── server.py          # FastMCP app + stdio transport
├── config.py          # pydantic-settings: typed env loading
├── logging.py         # structlog config (stderr, text or JSON)
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

## Operational notes

- **Rate limit.** The Plugin API caps at 500 requests per 5-minute rolling window per secret. `search_payments` mitigates burn by stopping as soon as it crosses the date floor or hits its result cap, but a long unbounded scan can still exhaust the budget. `tebex_tool_error` surfaces 429s explicitly.
- **One process per store.** Each MCP client entry spawns its own `tebex-mcp` subprocess with the store's secret in its environment. To switch stores, switch entries — there is no runtime store selection inside a process.
- **Graceful shutdown.** `SIGTERM` / `SIGINT` closes the httpx client and FastMCP session, then exits.

## License

Private. © Mediavee.
