/**
 * Signal CLI Tool - 信号测试相关命令
 *
 * 从 quant-cli-tool 中拆分出的信号测试命令
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../quant/quant-v2-client.js";
import { wrapToolExecution, validateParams } from "../shared/error-handler.js";

type CommandRule = {
  domain: string;
  action: string;
  description: string;
  params: Record<string, any>;
  example: Record<string, unknown>;
};

const SIGNAL_COMMANDS: Record<string, CommandRule> = {
  "signal.list": {
    domain: "signal",
    action: "list",
    description: "查询历史信号记录（支持按日期、状态筛选）。",
    params: {
      date: { type: "string" },
      status: { type: "string", enum: ["pending", "executed", "expired"] },
      limit: { type: "integer", min: 1 }
    },
    example: { date: "2026-06-01", status: "pending", limit: 20 },
  },
  "signal.arbitrate": {
    domain: "signal",
    action: "arbitrate",
    description: "对已生成的交易信号进行仲裁：按股票聚合同日 BUY/SELL 信号，处理冲突并给出最终裁决。",
    params: {
      date: { type: "string" },
      signals_dir: { type: "string" },
      signals_json: { type: "string" },
      min_confidence_gap: { type: "number", min: 0 },
    },
    example: { date: "2026-05-20" },
  },
  "signal.statistics": {
    domain: "signal",
    action: "statistics",
    description: "信号准确率统计（按策略/时间段聚合）。",
    params: {
      strategy_id: { type: "string" },
      start_date: { type: "string" },
      end_date: { type: "string" }
    },
    example: { strategy_id: "53", start_date: "2026-05-01", end_date: "2026-05-31" },
  },
};

export const signalCliTool: ToolDefinition = {
  name: "signal_cli",
  label: "信号测试管理",
  description:
    "管理交易信号：查询历史信号、信号仲裁、准确率统计。" +
    "适用场景：信号回测、准确率分析、冲突处理。",

  parameters: Type.Object({
    command: Type.Union(
      Object.keys(SIGNAL_COMMANDS).map(cmd => Type.Literal(cmd)) as any,
      { description: "信号管理命令" }
    ),
    params: Type.Optional(
      Type.Record(Type.String(), Type.Any(), {
        description: "命令参数"
      })
    )
  }),

  execute: async (_toolCallId, input: any) => {
    return wrapToolExecution(
      async () => {
        const { command, params = {} } = input as { command: string; params?: Record<string, any> };
        const rule = SIGNAL_COMMANDS[command];

        if (!rule) {
          throw new Error(`未知的信号命令: ${command}`);
        }

        // 废弃警告
        if (rule.deprecated) {
          console.warn(`[DEPRECATED] ${command} 命令已废弃，请使用 ${rule.replacement}`);
        }

        // 验证必填参数
        const requiredFields: string[] = [];
        for (const [key, paramRule] of Object.entries(rule.params)) {
          if ((paramRule as any).required) {
            requiredFields.push(key);
          }
        }

        if (requiredFields.length > 0) {
          validateParams(params).required(requiredFields).validate();
        }

        // 调用 v2 API
        const response = await runQuantV2(command, params);

        return {
          content: [{
            type: "text" as const,
            text: typeof response === 'string'
              ? response
              : JSON.stringify(response, null, 2)
          }],
          details: response
        };
      },
      {
        toolName: "signal_cli",
        enablePerformanceMonitoring: true,
        errorSuggestion: "如果信号生成失败，请确认策略ID是否正确，quantsys-v2 服务是否运行。"
      }
    );
  }
};
