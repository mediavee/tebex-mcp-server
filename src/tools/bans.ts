import { z } from "zod";
import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerBanTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "list_bans",
    "List all bans with id, time, ip, email, reason, and user info.",
    {},
    async () => {
      const data = await ctx.client.listBans();
      return jsonResult(data);
    },
  );

  server.tool(
    "create_ban",
    "Ban a user or IP from the store.",
    {
      reason: z.string().describe("Reason for the ban"),
      ip: z.string().optional().describe("IP address to ban"),
      user: z
        .string()
        .optional()
        .describe("Username or UUID of the player to ban"),
    },
    async ({ reason, ip, user }) => {
      const data = await ctx.client.createBan({ reason, ip, user });
      return jsonResult(data);
    },
  );
};
