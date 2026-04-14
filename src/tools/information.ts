import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerInformationTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "get_store_info",
    "Get store account and server information: store id, name, domain, currency, " +
      "game type, online mode, and linked server details. " +
      "Use this to verify the connection and discover store configuration.",
    {},
    async () => {
      const data = await ctx.client.getInformation();
      return jsonResult(data);
    },
  );
};
