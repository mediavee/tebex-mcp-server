import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerInformationTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "get_store_info",
    "Get store and server info: id, name, domain, currency, game type, online mode.",
    {},
    async () => {
      const data = await ctx.client.getInformation();
      return jsonResult(data);
    },
  );
};
