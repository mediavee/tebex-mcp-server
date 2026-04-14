import { z } from "zod";
import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerCouponTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "list_coupons",
    "List all coupons (paginated). Returns code, discount type/amount, " +
      "effective scope, expiration, and usage stats.",
    {},
    async () => {
      const data = await ctx.client.listCoupons();
      return jsonResult(data);
    },
  );

  server.tool(
    "get_coupon",
    "Get full details of a single coupon by its ID.",
    {
      coupon_id: z.number().int().describe("Coupon ID"),
    },
    async ({ coupon_id }) => {
      const data = await ctx.client.getCoupon(coupon_id);
      return jsonResult(data);
    },
  );

  server.tool(
    "create_coupon",
    "Create a new coupon with full configuration: code, discount type, " +
      "scope (package/category/cart), limits, date range, and more.",
    {
      code: z.string().describe("Coupon code customers will enter"),
      effective_on: z
        .enum(["package", "category", "cart"])
        .describe("What the coupon applies to"),
      packages: z
        .array(z.number().int())
        .optional()
        .describe("Package IDs the coupon applies to (when effective_on=package)"),
      categories: z
        .array(z.number().int())
        .optional()
        .describe("Category IDs the coupon applies to (when effective_on=category)"),
      discount_type: z
        .enum(["value", "percentage"])
        .describe("Whether the discount is a fixed value or a percentage"),
      discount_amount: z
        .number()
        .optional()
        .describe("Fixed discount amount (when discount_type=value)"),
      discount_percentage: z
        .number()
        .min(0)
        .max(100)
        .optional()
        .describe("Discount percentage (when discount_type=percentage)"),
      redeem_unlimited: z
        .boolean()
        .describe("If true, coupon can be redeemed unlimited times"),
      expire_never: z
        .boolean()
        .describe("If true, coupon never expires"),
      expire_limit: z
        .number()
        .int()
        .optional()
        .describe("Max number of redemptions (when redeem_unlimited=false)"),
      expire_date: z
        .string()
        .optional()
        .describe("Expiration date (when expire_never=false)"),
      start_date: z.string().optional().describe("Start date for the coupon"),
      basket_type: z
        .enum(["single", "subscription", "both"])
        .describe("Which basket types the coupon works with"),
      minimum: z
        .number()
        .min(0)
        .describe("Minimum basket value for the coupon to apply"),
      discount_application_method: z
        .number()
        .int()
        .describe("Application method: 0 = apply to each package, 1 = apply to basket total, 2 = apply once to most expensive"),
      username: z
        .string()
        .optional()
        .describe("Restrict coupon to a specific username"),
      note: z.string().optional().describe("Internal note"),
    },
    async (params) => {
      const data = await ctx.client.createCoupon(params);
      return jsonResult(data);
    },
  );

  server.tool(
    "delete_coupon",
    "Delete a coupon. Once deleted, the code can no longer be redeemed.",
    {
      coupon_id: z.number().int().describe("Coupon ID"),
    },
    async ({ coupon_id }) => {
      await ctx.client.deleteCoupon(coupon_id);
      return jsonResult({ ok: true, coupon_id, deleted: true });
    },
  );
};
