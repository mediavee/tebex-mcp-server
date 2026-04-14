import { z } from "zod";
import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerCommunityGoalTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "list_community_goals",
    "List all community goals with target, progress, status, and times achieved.",
    {},
    async () => {
      const data = await ctx.client.listCommunityGoals();
      return jsonResult(data);
    },
  );

  server.tool(
    "get_community_goal",
    "Get community goal details by ID.",
    {
      goal_id: z.number().int().describe("Community goal ID"),
    },
    async ({ goal_id }) => {
      const data = await ctx.client.getCommunityGoal(goal_id);
      return jsonResult(data);
    },
  );
};
