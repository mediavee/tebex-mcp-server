import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerSaleTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "list_sales",
    "List all active sales in the store. Returns sale id, name, effective " +
      "scope (packages/categories), discount type and value, and start/expire dates.",
    {},
    async () => {
      const data = await ctx.client.listSales();
      return jsonResult(data);
    },
  );
};
