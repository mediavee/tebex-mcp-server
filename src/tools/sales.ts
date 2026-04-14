import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerSaleTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "list_sales",
    "List active sales with scope, discount, and start/expire dates.",
    {},
    async () => {
      const data = await ctx.client.listSales();
      return jsonResult(data);
    },
  );
};
