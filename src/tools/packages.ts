import { z } from "zod";
import { type ToolRegistrar, jsonResult } from "./context.js";

export const registerPackageTools: ToolRegistrar = (server, ctx) => {
  server.tool(
    "list_categories",
    "List all categories and their packages as displayed on the webstore. " +
      "Returns the full category tree with nested package summaries.",
    {},
    async () => {
      const data = await ctx.client.getListing();
      return jsonResult(data);
    },
  );

  server.tool(
    "list_packages",
    "List all packages in the store with full details: id, name, price, " +
      "image, description, type, category, and sale info.",
    {},
    async () => {
      const data = await ctx.client.listPackages();
      return jsonResult(data);
    },
  );

  server.tool(
    "get_package",
    "Get full details of a single package by its ID.",
    {
      package_id: z.number().int().describe("Package ID"),
    },
    async ({ package_id }) => {
      const data = await ctx.client.getPackage(package_id);
      return jsonResult(data);
    },
  );

  server.tool(
    "update_package",
    "Update a package's properties. Only provided fields are changed. " +
      "Can toggle disabled state, rename, or change price.",
    {
      package_id: z.number().int().describe("Package ID"),
      disabled: z
        .boolean()
        .optional()
        .describe("Set to true to disable the package on the webstore"),
      name: z.string().optional().describe("New package name"),
      price: z
        .number()
        .min(0)
        .optional()
        .describe("New price in store currency"),
    },
    async ({ package_id, disabled, name, price }) => {
      await ctx.client.updatePackage(package_id, { disabled, name, price });
      return jsonResult({
        ok: true,
        package_id,
        updated: { disabled, name, price },
      });
    },
  );
};
