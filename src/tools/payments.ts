import { z } from "zod";
import type { PaymentEntry } from "../tebex/client.js";
import { type ToolRegistrar, jsonResult, errorResult } from "./context.js";

export const registerPaymentTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "search_payments",
    "Filter payments by username, date range, package, status, and/or amount. " +
      "Paginates automatically with early-exit on date boundary. Check `has_more` for more results.",
    {
      username: z
        .string()
        .optional()
        .describe("Filter by player username (case-insensitive partial match)"),
      from: z
        .string()
        .optional()
        .describe("Only payments on or after this date (ISO 8601, e.g. 2026-04-01)"),
      to: z
        .string()
        .optional()
        .describe("Only payments on or before this date (ISO 8601, e.g. 2026-04-14)"),
      package_id: z
        .number()
        .int()
        .optional()
        .describe("Filter by package ID"),
      status: z
        .enum(["complete", "chargeback", "refund"])
        .optional()
        .describe("Filter by payment status"),
      min_amount: z
        .number()
        .optional()
        .describe("Minimum payment amount"),
      max_amount: z
        .number()
        .optional()
        .describe("Maximum payment amount"),
      limit: z
        .number()
        .int()
        .min(1)
        .max(100)
        .optional()
        .describe("Max results to return (default: 25)"),
      max_pages: z
        .number()
        .int()
        .min(1)
        .max(50)
        .optional()
        .describe("Max pages to scan (default: 20, each page = 25 payments)"),
    },
    async ({ username, from, to, package_id, status, min_amount, max_amount, limit, max_pages }) => {
      const maxResults = limit ?? 25;
      const maxScan = max_pages ?? 20;

      const fromDate = from ? new Date(from) : null;
      const toDate = to ? new Date(to) : null;

      if (fromDate && Number.isNaN(fromDate.getTime())) {
        return errorResult("Invalid 'from' date format. Use ISO 8601 (e.g. 2026-04-01).");
      }
      if (toDate && Number.isNaN(toDate.getTime())) {
        return errorResult("Invalid 'to' date format. Use ISO 8601 (e.g. 2026-04-14).");
      }

      // Normalize toDate to end of day
      if (toDate) toDate.setHours(23, 59, 59, 999);

      const usernameLower = username?.toLowerCase();
      const results: PaymentEntry[] = [];
      let scanned = 0;
      let pagesScanned = 0;
      let hitDateBoundary = false;
      let reachedEnd = false;

      for (let page = 1; page <= maxScan; page++) {
        const response = await ctx.client.listPaymentsPaged(page);
        pagesScanned++;

        if (!response.data || response.data.length === 0) {
          reachedEnd = true;
          break;
        }

        for (const payment of response.data) {
          scanned++;
          const paymentDate = new Date(payment.date);

          // Early exit: payments are sorted desc, so if we're past the from date, stop
          if (fromDate && paymentDate < fromDate) {
            hitDateBoundary = true;
            break;
          }

          // Skip if before toDate
          if (toDate && paymentDate > toDate) continue;

          // Apply filters
          if (usernameLower && !payment.player?.name?.toLowerCase().includes(usernameLower)) continue;
          if (status && payment.status !== status) continue;
          if (package_id && !payment.packages?.some((p) => p.id === package_id)) continue;

          const amount = Number.parseFloat(payment.price);
          if (min_amount !== undefined && amount < min_amount) continue;
          if (max_amount !== undefined && amount > max_amount) continue;

          results.push(payment);
          if (results.length >= maxResults) break;
        }

        if (hitDateBoundary || results.length >= maxResults) break;
        if (page >= response.pagination.last_page) {
          reachedEnd = true;
          break;
        }
      }

      const hasMore = !hitDateBoundary && !reachedEnd && results.length >= maxResults;

      return jsonResult({
        results,
        meta: {
          matched: results.length,
          scanned,
          pages_scanned: pagesScanned,
          has_more: hasMore,
        },
      });
    },
  );

  server.tool(
    "list_payments",
    "Get the latest payments (up to 100): transaction id, amount, date, player, packages.",
    {
      limit: z
        .number()
        .int()
        .min(1)
        .max(100)
        .optional()
        .describe("Max number of payments to return (default: 100)"),
    },
    async ({ limit }) => {
      const data = await ctx.client.listPayments(limit);
      return jsonResult(data);
    },
  );

  server.tool(
    "list_payments_paged",
    "Get payments with pagination (25 per page).",
    {
      page: z
        .number()
        .int()
        .min(1)
        .optional()
        .describe("Page number (1-indexed, default: 1)"),
    },
    async ({ page }) => {
      const data = await ctx.client.listPaymentsPaged(page);
      return jsonResult(data);
    },
  );

  server.tool(
    "get_payment",
    "Get full payment details: player, packages, amount, status, date, notes.",
    {
      transaction_id: z
        .string()
        .describe("Transaction ID (e.g. tbx-abc123)"),
    },
    async ({ transaction_id }) => {
      const data = await ctx.client.getPayment(transaction_id);
      return jsonResult(data);
    },
  );

  server.tool(
    "get_payment_fields",
    "Get required `options` fields for create_payment on a given package.",
    {
      package_id: z.number().int().describe("Package ID"),
    },
    async ({ package_id }) => {
      const data = await ctx.client.getPaymentFields(package_id);
      return jsonResult(data);
    },
  );

  server.tool(
    "create_payment",
    "Create a manual payment — assign packages to a player without checkout.",
    {
      ign: z
        .string()
        .describe("In-game name (username) of the player receiving the packages"),
      packages: z
        .array(
          z.object({
            id: z.number().int().describe("Package ID"),
            options: z
              .record(z.string())
              .describe("Package-specific options (use get_payment_fields to discover them)"),
          }),
        )
        .min(1)
        .describe("Packages to assign"),
      price: z.number().min(0).describe("Total price for this payment"),
      note: z.string().describe("Internal note for this payment"),
    },
    async ({ ign, packages, price, note }) => {
      await ctx.client.createPayment({ ign, packages, price, note });
      return jsonResult({ ok: true, ign, packages_count: packages.length });
    },
  );

  server.tool(
    "update_payment",
    "Update a payment's username or status (complete/chargeback/refund).",
    {
      transaction_id: z.string().describe("Transaction ID"),
      username: z.string().optional().describe("New username"),
      status: z
        .enum(["complete", "chargeback", "refund"])
        .optional()
        .describe("New payment status"),
    },
    async ({ transaction_id, username, status }) => {
      await ctx.client.updatePayment(transaction_id, { username, status });
      return jsonResult({ ok: true, transaction_id, updated: { username, status } });
    },
  );

  server.tool(
    "add_payment_note",
    "Add a note to a payment.",
    {
      transaction_id: z.string().describe("Transaction ID"),
      note: z.string().describe("Note text to add"),
    },
    async ({ transaction_id, note }) => {
      const data = await ctx.client.addPaymentNote(transaction_id, note);
      return jsonResult(data);
    },
  );

  server.tool(
    "create_checkout",
    "Generate a checkout URL for a player and package. Returns URL and expiration.",
    {
      package_id: z.number().int().describe("Package ID"),
      username: z.string().describe("Player username"),
    },
    async ({ package_id, username }) => {
      const data = await ctx.client.createCheckout(package_id, username);
      return jsonResult(data);
    },
  );
};
