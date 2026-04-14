import { randomUUID } from "node:crypto";
import express, { type Request, type Response } from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";

import { loadConfig } from "./config.js";
import { TebexClient } from "./tebex/client.js";
import { bearerAuth } from "./auth.js";
import { registerAllTools } from "./tools/register.js";
import type { ToolContext } from "./tools/context.js";

const SERVER_INFO = {
  name: "tebex-mcp",
  version: "0.1.0",
};

async function main(): Promise<void> {
  const config = loadConfig();
  const client = new TebexClient(config);

  const ctx: ToolContext = { config, client };

  // ─────────────────────────── HTTP setup ───────────────────────────

  const app = express();
  app.use(express.json({ limit: "4mb" }));

  app.get("/healthz", (_req, res) => {
    res.json({ status: "ok", uptime: process.uptime() });
  });

  app.use("/mcp", bearerAuth(config.authToken));

  const transports = new Map<string, StreamableHTTPServerTransport>();

  app.post("/mcp", async (req: Request, res: Response) => {
    try {
      const sessionId = req.header("mcp-session-id");
      let transport: StreamableHTTPServerTransport;

      if (sessionId && transports.has(sessionId)) {
        transport = transports.get(sessionId)!;
      } else if (!sessionId && isInitializeRequest(req.body)) {
        transport = new StreamableHTTPServerTransport({
          sessionIdGenerator: () => randomUUID(),
          onsessioninitialized: (id: string) => {
            transports.set(id, transport);
            console.log(`[mcp] session initialized: ${id}`);
          },
        });
        transport.onclose = () => {
          if (transport.sessionId) {
            transports.delete(transport.sessionId);
            console.log(`[mcp] session closed: ${transport.sessionId}`);
          }
        };

        const mcp = new McpServer(SERVER_INFO);
        registerAllTools(mcp, ctx);
        await mcp.connect(transport);
      } else {
        res.status(400).json({
          jsonrpc: "2.0",
          error: {
            code: -32000,
            message: "Bad Request: missing or invalid session id",
          },
          id: null,
        });
        return;
      }

      await transport.handleRequest(req, res, req.body);
    } catch (err) {
      console.error("[mcp] POST /mcp failed:", err);
      if (!res.headersSent) {
        res.status(500).json({
          jsonrpc: "2.0",
          error: { code: -32603, message: "Internal error" },
          id: null,
        });
      }
    }
  });

  const handleSessionRequest = async (req: Request, res: Response) => {
    const sessionId = req.header("mcp-session-id");
    if (!sessionId || !transports.has(sessionId)) {
      res.status(400).send("Invalid or missing session id");
      return;
    }
    try {
      await transports.get(sessionId)!.handleRequest(req, res);
    } catch (err) {
      console.error("[mcp] session request failed:", err);
      if (!res.headersSent) res.status(500).end();
    }
  };

  app.get("/mcp", handleSessionRequest);
  app.delete("/mcp", handleSessionRequest);

  const server = app.listen(config.httpPort, config.httpHost, () => {
    console.log(
      `[tebex-mcp] listening on http://${config.httpHost}:${config.httpPort}/mcp`,
    );
  });

  // ─────────────────────────── Shutdown ───────────────────────────

  const shutdown = (signal: string) => {
    console.log(`[tebex-mcp] received ${signal}, shutting down`);
    server.close(() => {
      for (const transport of transports.values()) {
        try {
          transport.close();
        } catch {
          // ignore
        }
      }
      transports.clear();
      process.exit(0);
    });
    server.closeAllConnections?.();
    setTimeout(() => {
      console.error("[tebex-mcp] forced exit after timeout");
      process.exit(1);
    }, 10_000).unref();
  };

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT", () => shutdown("SIGINT"));
}

main().catch((err) => {
  console.error("[tebex-mcp] fatal:", err);
  process.exit(1);
});
