import { z } from "zod";
import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerCommandQueueTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "get_command_queue",
    "Get due player command queue: players with pending commands, next check interval.",
    {},
    async () => {
      const data = await ctx.client.getCommandQueue();
      return jsonResult(data);
    },
  );

  server.tool(
    "get_offline_commands",
    "Get commands executable without the player online: id, string, payment, package, conditions.",
    {},
    async () => {
      const data = await ctx.client.getOfflineCommands();
      return jsonResult(data);
    },
  );

  server.tool(
    "get_online_commands",
    "Get pending commands for a specific player (requires player online).",
    {
      player_id: z
        .number()
        .int()
        .describe("Tebex player ID"),
    },
    async ({ player_id }) => {
      const data = await ctx.client.getOnlineCommands(player_id);
      return jsonResult(data);
    },
  );

  server.tool(
    "delete_commands",
    "Remove executed commands from the queue.",
    {
      ids: z
        .array(z.number().int())
        .min(1)
        .describe("Array of command IDs to remove from the queue"),
    },
    async ({ ids }) => {
      await ctx.client.deleteCommands(ids);
      return jsonResult({ ok: true, deleted_count: ids.length, ids });
    },
  );
};
