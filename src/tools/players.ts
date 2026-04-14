import { z } from "zod";
import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerPlayerTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "lookup_player",
    "Look up a player by username or UUID: bans, chargeback rate, payments, purchase totals. Ultimate plan only.",
    {
      identifier: z
        .string()
        .describe("Player username or UUID"),
    },
    async ({ identifier }) => {
      const data = await ctx.client.lookupPlayer(identifier);
      return jsonResult(data);
    },
  );

  server.tool(
    "get_player_packages",
    "List active packages owned by a player. Optionally filter by package ID.",
    {
      player_id: z.number().int().describe("Tebex player ID (from lookup_player)"),
      package_id: z
        .number()
        .int()
        .optional()
        .describe("Filter to a specific package ID"),
    },
    async ({ player_id, package_id }) => {
      const data = await ctx.client.getPlayerPackages(player_id, package_id);
      return jsonResult(data);
    },
  );
};
