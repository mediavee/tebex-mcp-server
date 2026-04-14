import { z } from "zod";
import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerCommandQueueTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "get_command_queue",
    "Get the due player command queue. Returns a list of players with pending " +
      "commands, the next check interval, and whether offline execution is enabled. " +
      "This is the entry point for the command delivery flow.",
    {},
    async () => {
      const data = await ctx.client.getCommandQueue();
      return jsonResult(data);
    },
  );

  server.tool(
    "get_offline_commands",
    "Get commands that can be executed immediately (offline commands). " +
      "These don't require the player to be online. Returns command id, " +
      "string, associated payment and package, and delay/slot conditions.",
    {},
    async () => {
      const data = await ctx.client.getOfflineCommands();
      return jsonResult(data);
    },
  );

  server.tool(
    "get_online_commands",
    "Get pending commands for a specific player (online commands). " +
      "These require the player to be online to execute.",
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
    "Mark commands as executed and remove them from the queue. " +
      "Call this after successfully running the commands on the game server.",
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
