import { Type } from "@sinclair/typebox";
import { execSync } from "child_process";
import type { ToolDefinition } from "./index.js";

export const manageStockDBTool: ToolDefinition = {
  name: "manage_stock_db",
  label: "股票数据库管理",
  description: "管理股票数据库 Pipeline，支持执行全量更新和查看状态。",
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("pipeline_update"),
      Type.Literal("pipeline_status"),
    ], { description: "pipeline_update=执行全量更新, pipeline_status=查看状态" }),
    market: Type.Optional(Type.String({ description: "市场标识，例如 A 或 HK（pipeline_update 时必需）" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const { action, market } = params;

    if (action === "pipeline_update") {
      const output = execSync(`python pipeline/pipeline.py full --market ${market}`, {
        cwd: process.cwd(),
        encoding: "utf-8",
      });
      return { content: [{ type: "text" as const, text: output }], details: undefined };
    }

    const output = execSync("python pipeline/pipeline.py status", {
      cwd: process.cwd(),
      encoding: "utf-8",
    });
    return { content: [{ type: "text" as const, text: output }], details: undefined };
  },
};

export const stockDBTools: ToolDefinition[] = [manageStockDBTool];
