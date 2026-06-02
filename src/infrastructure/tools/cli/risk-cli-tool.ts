/**
 * Risk Management CLI Tool
 *
 * 风控管理命令：风险检查、监控、限制、告警
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../quant/quant-v2-client.js";
import { formatMaybeLargeToolOutput } from "../shared/large-tool-output.js";

const RISK_COMMANDS = {
  "risk.check": {
    domain: "risk",
    action: "check",
    description: "风险检查：检查持仓风险指标（集中度、行业分布、波动率）。",
    params: {
      portfolio_id: { type: "string" },
    },
    example: { portfolio_id: "default" },
  },
  "risk.monitor": {
    domain: "risk",
    action: "monitor",
    description: "风险监控：实时监控持仓风险变化。",
    params: {
      portfolio_id: { type: "string" },
      threshold: { type: "number", min: 0 },
    },
    example: { portfolio_id: "default", threshold: 0.1 },
  },
  "risk.limit": {
    domain: "risk",
    action: "limit",
    description: "风险限制：设置或查询风险限制（最大持仓、最大回撤等）。",
    params: {
      action: { type: "string", enum: ["get", "set"] },
      limit_type: { type: "string" },
      value: { type: "number" },
    },
    example: { action: "set", limit_type: "max_drawdown", value: 0.2 },
  },
  "risk.alert": {
    domain: "risk",
    action: "alert",
    description: "风险告警：查询或设置风险告警规则。",
    params: {
      alert_type: { type: "string" },
      enabled: { type: "boolean" },
    },
    example: { alert_type: "volatility_spike", enabled: true },
  },
};

export const riskCliTool: ToolDefinition = {
  name: "risk_cli",
  label: "风险管理 CLI",
  description:
    "风险管理命令行工具，支持 4 个命令：" +
    "risk.check（风险检查）、risk.monitor（风险监控）、" +
    "risk.limit（风险限制）、risk.alert（风险告警）。" +
    "通过 command 参数指定命令，params 参数传递命令参数。",

  parameters: Type.Object({
    command: Type.String({
      description: `命令名称，可选值：${Object.keys(RISK_COMMANDS).join(", ")}`,
    }),
    params: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "命令参数对象",
      })
    ),
  }),

  execute: async (_toolCallId, rawParams) => {
    const { command, params = {} } = rawParams;

    // 验证命令
    const rule = RISK_COMMANDS[command as keyof typeof RISK_COMMANDS];
    if (!rule) {
      return {
        content: [{
          type: "text" as const,
          text: `不支持的风险命令: ${command}\n\n可用命令: ${Object.keys(RISK_COMMANDS).join(", ")}`
        }],
        details: undefined
      };
    }

    try {
      // 调用后端 API
      const result = await runQuantV2(rule.domain, rule.action, params);

      // 格式化输出
      const output = formatMaybeLargeToolOutput(JSON.stringify(result, null, 2));

      return {
        content: [{ type: "text" as const, text: output }],
        details: result
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `❌ 风险命令执行失败\n\n命令: ${command}\n错误: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  },
};
