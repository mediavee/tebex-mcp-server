---
name: tebex-store-ops
description: Operate a Tebex web store via the Plugin API — look up payments and players, refund or chargeback transactions, grant or revoke packages, manage gift cards, coupons, bans, sales, community goals, and the player command queue. Use when the user mentions Tebex, a transaction id (`tbx-…`), a refund or chargeback, a player not receiving their purchase, a store coupon or sale, or any moderation action on the store.
---

# Tebex store operations

You have access to the `tebex-mcp` MCP server, which wraps the [Tebex Plugin API](https://docs.tebex.io/developers/plugin-api/endpoints) (`https://plugin.tebex.io`). The server is per-store: one running instance talks to exactly one Tebex secret.

## When to use this skill

Triggers (any language):

- "refund this payment / cette transaction"
- "the player didn't get their package / rank / kit"
- "look up payments for username X"
- "create a coupon / launch a promo"
- "ban this user from the store"
- "show me last month's revenue / chargebacks"
- A bare transaction id like `tbx-abc123`

If the user is asking about **in-game delivery mechanics** (the plugin running on the game server, command execution on the Minecraft side), this skill can only confirm what Tebex sent — anything past `get_command_queue` belongs to the game server's tooling.

## Tool inventory

### Information & catalog
- `get_store_info` — store metadata, currency, game type, online mode.
- `list_categories` — categories with nested package summaries.
- `list_packages`, `get_package` — package catalog and details.
- `update_package` — toggle disabled, rename, change price (partial update).

### Payments
- `search_payments` — **the one to use most of the time**. Filters: `username` (substring, case-insensitive), `from`/`to` (ISO date), `package_id`, `status`, `min_amount`/`max_amount`. Auto-paginates with early-exit when payments cross the lower date bound. Returns `{results, meta:{matched, scanned, pages_scanned, has_more}}`.
- `list_payments` — newest payments capped at 100. Use only when you genuinely want "the latest activity, no filter".
- `list_payments_paged` — raw 25-per-page pagination. Rarely needed; `search_payments` is almost always better.
- `get_payment` — full details for a `tbx-…` transaction id.
- `get_payment_fields` — required `options` keys for `create_payment` on a given package.
- `create_payment` — manual payment (assign packages without going through checkout).
- `update_payment` — change `username` or `status` (`complete` / `chargeback` / `refund`).
- `add_payment_note` — append an internal note to a payment.
- `create_checkout` — generate a hosted checkout URL for a player + package.

### Gift cards
- `list_gift_cards`, `get_gift_card`, `lookup_gift_card` (by customer-facing code), `create_gift_card`, `topup_gift_card`, `void_gift_card`.

### Coupons
- `list_coupons`, `get_coupon`, `create_coupon`, `delete_coupon`.

### Bans
- `list_bans`, `create_ban` (user, IP, or both).

### Sales
- `list_sales` — active sales with scope and dates.

### Community goals
- `list_community_goals`, `get_community_goal`.

### Players & command queue
- `lookup_player` — username or UUID → bans, chargeback rate, payments, totals (Ultimate plan).
- `get_player_packages` — active packages owned by a Tebex player id (optionally filtered by package).
- `get_command_queue` — players with pending commands and the next-check interval.
- `get_offline_commands` — commands runnable without the player online.
- `get_online_commands` — pending commands for one player (requires player online).
- `delete_commands` — bulk-remove command ids from the queue (after they ran).

## The one thing that trips everyone up

**There are three different player identifiers in Tebex and they are not interchangeable.** Mistaking one for another is the most common cause of 404s and empty results.

| Identifier | Type | Where it comes from | What accepts it |
|---|---|---|---|
| `txn_id` (e.g. `tbx-abc123`) | string | `payment.txn_id` from any payments listing | `get_payment`, `update_payment`, `add_payment_note` |
| `player.id` (e.g. `1234567`) | int | `payment.player.id`, `lookup_player` response | `get_player_packages`, `get_online_commands` |
| in-game name / UUID (e.g. `Notch`, `069a79f4-…`) | string | The player tells you, or you read it from the game server | `lookup_player`, `create_payment` (`ign`), `create_checkout` (`username`), `create_ban` (`user`) |

When the user gives you a username, you usually need to **resolve it to a Tebex player id first** (via `lookup_player` if available, or by pulling it out of a recent payment via `search_payments`) before you can call `get_player_packages` or the per-player command queue tools.

## Methodology

### Refund or chargeback a payment

1. If the user gave you a **transaction id** directly: `get_payment(transaction_id)` to confirm amount, packages, and current status.
2. If the user gave you a **username** or vague description ("the guy who bought VIP yesterday"): `search_payments(username=…, from=…)` to surface the candidate, then `get_payment` on the txn id.
3. Show the user what you found (amount, package, date) and confirm which status to apply: `refund` (the buyer's request) or `chargeback` (forced by the bank).
4. `update_payment(transaction_id, status="refund" | "chargeback")`.
5. If you're not sure what changed downstream, fetch the payment again (`get_payment`) — Tebex usually flags packages for revocation automatically when a payment moves out of `complete`.

### Debug "the player didn't get their package"

Symptom: a customer paid but their in-game grade / kit / item is missing.

1. **Find the payment.** Either `get_payment(txn_id)` if they have it, or `search_payments(username=…, status="complete")` to locate the most recent successful purchase.
2. **Check the username on the payment first.** This is the #1 cause of "I didn't get my package" — at checkout, the customer typed their username **themselves** and they often typo it (`Notch_` instead of `Notch`, an old name they don't use anymore, a Bedrock-style `.PlayerName`, the wrong account entirely). The package was delivered correctly to the username they entered, just not to the one they're playing on. Compare `payment.player.name` (what Tebex received) to the username the user is currently complaining about — if they differ, that's your answer. Fix with `update_payment(transaction_id, username=<correct ign>)` and the commands will re-route to the right player.
3. **Check ownership in Tebex's view.** If the username matches, resolve the Tebex `player.id` from the payment, then `get_player_packages(player_id)` — does Tebex think the player owns this package? If yes, the issue is downstream (game server didn't apply commands).
4. **Inspect the command queue.** The Tebex plugin on the game server polls Tebex for commands to execute. Check both:
   - `get_offline_commands` — commands queued for delivery without the player online (common for "give item" actions that wait until login).
   - `get_online_commands(player_id)` — commands waiting for the player to be online.
5. **Cross-reference timestamps.** If the command sits in `get_offline_commands` long after the payment, the in-game plugin isn't polling — that's a game-server config issue, not a Tebex issue.
6. If commands have been delivered but the in-game state is still wrong, hand off — that's a game-side problem (plugin config, missing permissions, wrong group name).

### Grant a package manually (no checkout)

Use case: comp a streamer, fulfil a giveaway, replace a package lost in a botched refund.

1. `get_payment_fields(package_id)` — the package may require fields like `email` or a custom selector. The response tells you the exact `options` keys you need to provide.
2. `create_payment(ign=<player username>, packages=[{id: <pkg>, options: {...}}], price=<amount>, note=<why>)`. Always include a meaningful `note` — Future-you will thank Past-you.
3. The packages flow through Tebex's normal delivery pipeline (command queue), so the same debugging steps as above apply if the player doesn't see them.

### Create a promotion

Two mechanisms, different scopes:

- **Sales** (`list_sales`) — store-wide or category/package-wide percentage discounts with start/end dates. Created **in the Tebex web dashboard**, not via this MCP. Use `list_sales` to inspect what's already running before adding overlap.
- **Coupons** (`create_coupon`) — code-based discounts customers enter at checkout. Created via the API.

For a coupon, the parameters that matter most:

- `effective_on`: `package` (apply to specific package ids), `category`, or `cart` (apply to whole basket).
- `discount_type` + (`discount_amount` if `value`, `discount_percentage` if `percentage`).
- `redeem_unlimited` + (`expire_limit` if not unlimited): caps total redemptions across all customers.
- `expire_never` + (`expire_date` if not never): caps the calendar window.
- `basket_type`: `single`, `subscription`, or `both`.
- `discount_application_method`: `0` = each package, `1` = basket total, `2` = once on most expensive item. Most common is `1` for cart coupons, `0` for package coupons.

If the user describes a one-off "10% off this weekend, anyone can use it" → coupon with `redeem_unlimited=true`, `expire_never=false` and a date. If they describe "10€ off for player Notch as compensation" → coupon with `username="Notch"`, `expire_limit=1`.

### Audit transactions over a period

Use `search_payments` with a date range and let it paginate until it hits the floor:

```
search_payments(from="2026-04-01", to="2026-04-30", status="complete", limit=100, max_pages=20)
```

The early-exit on the lower bound (`from`) means the call stops scanning as soon as it crosses April 1st — no wasted pages. Inspect `meta.has_more` to know whether you need a second pass with a smaller window.

For revenue or volume aggregates, do the math client-side from the `results` array — Tebex doesn't expose pre-aggregated stats via this API. The `price` field on each payment is a **string** (currency-formatted), parse with care.

### Ban a fraudulent buyer

Pattern: someone abuses chargebacks or runs stolen-card purchases.

1. `search_payments(username=…, status="chargeback")` to confirm the pattern (multiple chargebacks across separate payments is the signal — one isolated chargeback is often a banking dispute, not fraud).
2. Pull the **IPs and player identifier** from `get_payment` on each suspicious transaction (the payment payload includes the buyer's IP).
3. `create_ban(reason=<short reason>, user=<username or UUID>, ip=<ip>)` — pass both `user` and `ip` in the same call to ban both vectors at once.
4. Optional: `add_payment_note` on the related payments documenting why they were chargebacked, so the next operator who looks knows the history.

## Reading tool output

Most Tebex Plugin API responses are flat JSON — no `data`/`attributes` envelope (unlike Pterodactyl). Exceptions:

- `list_payments_paged` (and `search_payments` internally) returns `{pagination: {current_page, last_page}, data: [...]}`.
- `search_payments` wraps results in `{results: [...], meta: {matched, scanned, pages_scanned, has_more}}`.
- Several "create" tools wrapped by this MCP return `{ok: true, ...}` with the input echoed back when Tebex itself returns 204 No Content (so you can chain).

Payment shape (the one you'll touch most):

```json
{
  "txn_id": "tbx-abc123",
  "date": "2026-04-12T14:32:01+00:00",
  "price": "9.99",
  "currency": "EUR",
  "status": "complete",
  "player": { "id": 1234567, "name": "Notch", "uuid": "069a79f4-…" },
  "packages": [ { "id": 4242, "name": "VIP" } ]
}
```

Note `price` is a **string**, `player.id` is an **int**, `txn_id` is a **string starting with `tbx-`**.

## Error shapes

- `404` from a `get_*` tool → the resource doesn't exist (wrong id, wrong identifier kind — see the IDs table above).
- `429` → rate limit (500 req / 5 min per secret). The MCP surfaces this as a clean message; back off and retry, or narrow your `search_payments` window.
- Other 4xx with a body usually means a validation failure on a `create_*` / `update_*` call. The body is logged and surfaced — read the message rather than guessing.
