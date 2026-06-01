/**
 * Indicator Sandbox Columns Tool — 查询沙箱可用列
 *
 * 获取指定股票在沙箱中可用的数据列（技术指标、财务指标）及其覆盖率。
 * 用于编写指标代码前了解可用数据。
 *
 * 从 quant_cli 的 indicators.sandbox_columns 提取为独立工具。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

interface SandboxColumnsParams {
  symbol: string;
}

export const indicatorSandboxColumnsTool: ToolDefinition = {
  name: "indicator_sandbox_columns",
  label: "沙箱可用列",
  description:
    "获取指定股票在沙箱中可用的数据列（技术指标、财务指标）及其覆盖率。" +
    "用于编写指标代码前了解可用数据。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）或港股（如 9988）",
    }),
  }),

  execute: async (_toolCallId, rawParams: SandboxColumnsParams) => {
    try {
      const result = await runQuantV2("indicators.sandbox_columns", rawParams as unknown as Record<string, unknown>);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(result.data ?? result, null, 2),
        }],
        details: undefined,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `查询沙箱可用列失败: ${errorMsg}`,
        }],
        details: undefined,
      };
    }
  },
};
