import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { Config } from "../config.js";
import type { TebexClient } from "../tebex/client.js";

export interface ToolContext {
  config: Config;
  client: TebexClient;
}

export type ToolRegistrar = (server: McpServer, ctx: ToolContext) => void;

export function jsonResult(data: unknown) {
  return {
    content: [
      {
        type: "text" as const,
        text: typeof data === "string" ? data : JSON.stringify(data, null, 2),
      },
    ],
  };
}

export function errorResult(message: string) {
  return {
    isError: true,
    content: [{ type: "text" as const, text: message }],
  };
}
