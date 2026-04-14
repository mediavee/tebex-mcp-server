import { z } from "zod";
import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerGiftCardTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "list_gift_cards",
    "List all gift cards in the store. Returns id, code, balance, " +
      "starting balance, note, and void status.",
    {},
    async () => {
      const data = await ctx.client.listGiftCards();
      return jsonResult(data);
    },
  );

  server.tool(
    "get_gift_card",
    "Get full details of a single gift card by its ID.",
    {
      gift_card_id: z.number().int().describe("Gift card ID"),
    },
    async ({ gift_card_id }) => {
      const data = await ctx.client.getGiftCard(gift_card_id);
      return jsonResult(data);
    },
  );

  server.tool(
    "lookup_gift_card",
    "Look up a gift card by its code (the code the customer enters at checkout).",
    {
      code: z.string().describe("Gift card code"),
    },
    async ({ code }) => {
      const data = await ctx.client.lookupGiftCard(code);
      return jsonResult(data);
    },
  );

  server.tool(
    "create_gift_card",
    "Create a new gift card with a specified amount, expiration date, and note.",
    {
      amount: z.number().min(0).describe("Gift card value in store currency"),
      expires_at: z
        .string()
        .describe("Expiration date in ISO 8601 format (e.g. 2025-12-31)"),
      note: z.string().describe("Internal note for this gift card"),
    },
    async ({ amount, expires_at, note }) => {
      const data = await ctx.client.createGiftCard({
        amount,
        expires_at,
        note,
      });
      return jsonResult(data);
    },
  );

  server.tool(
    "topup_gift_card",
    "Add funds to an existing gift card.",
    {
      gift_card_id: z.number().int().describe("Gift card ID"),
      amount: z.number().min(0).describe("Amount to add in store currency"),
    },
    async ({ gift_card_id, amount }) => {
      const data = await ctx.client.topupGiftCard(gift_card_id, amount);
      return jsonResult(data);
    },
  );

  server.tool(
    "void_gift_card",
    "Void (deactivate) a gift card. This is irreversible — the remaining " +
      "balance becomes unusable.",
    {
      gift_card_id: z.number().int().describe("Gift card ID"),
    },
    async ({ gift_card_id }) => {
      await ctx.client.voidGiftCard(gift_card_id);
      return jsonResult({ ok: true, gift_card_id, voided: true });
    },
  );
};
