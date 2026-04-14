import { z } from "zod";
import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerCommunityGoalTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "list_community_goals",
    "List all community goals. Returns id, name, description, target amount, " +
      "current progress, status, repeatability, and times achieved.",
    {},
    async () => {
      const data = await ctx.client.listCommunityGoals();
      return jsonResult(data);
    },
  );

  server.tool(
    "get_community_goal",
    "Get full details of a single community goal by its ID.",
    {
      goal_id: z.number().int().describe("Community goal ID"),
    },
    async ({ goal_id }) => {
      const data = await ctx.client.getCommunityGoal(goal_id);
      return jsonResult(data);
    },
  );
};
