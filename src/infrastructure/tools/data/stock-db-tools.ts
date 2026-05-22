import { Type } from "@sinclair/typebox";
import { execSync } from "child_process";
import type { ToolDefinition } from "../index.js";

export const manageStockDBTool: ToolDefinition = {
  name: "manage_stock_db",
  label: "股票数据库管理",
  description: "管理股票数据库 Pipeline，支持执行全量更新和查看状态。",
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("pipeline_update"),
      Type.Literal("pipeline_status"),
    ], {
      description: "操作类型（必需）: pipeline_update=执行全量更新, pipeline_status=查看状态",
      default: "pipeline_status"
    }),
    market: Type.Optional(Type.String({ description: "市场标识，例如 A 或 HK（pipeline_update 时必需）" })),
  }),
  execute: async (_toolCallId, params: any) => {
    // Parameter validation with default fallback
    if (!params || typeof params !== "object") {
      params = { action: "pipeline_status" };
    }

    const { action = "pipeline_status", market } = params;

    if (!action) {
      return {
        content: [{ type: "text" as const, text: "错误: action 参数是必需的。可选值: pipeline_update, pipeline_status" }],
        details: undefined,
      };
    }

    try {
      if (action === "pipeline_update") {
        if (!market) {
          return {
            content: [{ type: "text" as const, text: "错误: pipeline_update 需要 market 参数（A 或 HK）" }],
            details: undefined,
          };
        }
        // 禁用代理环境变量（akshare 需要直连）
        const env = { ...process.env };
        delete env.HTTP_PROXY;
        delete env.HTTPS_PROXY;
        delete env.http_proxy;
        delete env.https_proxy;
        delete env.ALL_PROXY;
        const output = execSync(`python quant/quantsys/data/pipeline.py full --market ${market}`, {
          cwd: process.cwd(),
          encoding: "utf-8",
          timeout: 300000, // 5 minutes timeout
          env,
        });
        return { content: [{ type: "text" as const, text: output }], details: undefined };
      }

      const output = execSync("python quant/quantsys/data/pipeline.py status", {
        cwd: process.cwd(),
        encoding: "utf-8",
        timeout: 10000, // 10 seconds timeout for status check
      });
      return { content: [{ type: "text" as const, text: output }], details: undefined };
    } catch (error: any) {
      const errorMessage = error.message || String(error);
      const stderr = error.stderr?.toString() || "";
      const stdout = error.stdout?.toString() || "";

      return {
        content: [{
          type: "text" as const,
          text: `执行失败:\n${errorMessage}\n${stderr ? `\nStderr: ${stderr}` : ""}${stdout ? `\nStdout: ${stdout}` : ""}`,
        }],
        details: undefined,
      };
    }
  },
};

export const stockDBTools: ToolDefinition[] = [manageStockDBTool];
