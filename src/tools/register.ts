import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { ToolContext } from "./context.js";
import { registerInformationTools } from "./information.js";
import { registerPackageTools } from "./packages.js";
import { registerPaymentTools } from "./payments.js";
import { registerGiftCardTools } from "./gift-cards.js";
import { registerCouponTools } from "./coupons.js";
import { registerBanTools } from "./bans.js";
import { registerSaleTools } from "./sales.js";
import { registerCommunityGoalTools } from "./community-goals.js";
import { registerPlayerTools } from "./players.js";
import { registerCommandQueueTools } from "./command-queue.js";

export function registerAllTools(server: McpServer, ctx: ToolContext): void {
  registerInformationTools(server, ctx);
  registerPackageTools(server, ctx);
  registerPaymentTools(server, ctx);
  registerGiftCardTools(server, ctx);
  registerCouponTools(server, ctx);
  registerBanTools(server, ctx);
  registerSaleTools(server, ctx);
  registerCommunityGoalTools(server, ctx);
  registerPlayerTools(server, ctx);
  registerCommandQueueTools(server, ctx);
}
