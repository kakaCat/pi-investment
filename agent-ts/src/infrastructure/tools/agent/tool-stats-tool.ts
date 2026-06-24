/**
 * 工具统计查询和报告工具
 *
 * 提供查询工具使用统计和生成报告的 Agent 工具
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { getStatsManager } from "../shared/tool-stats-manager.js";
import { formatTableOutput, formatStatsOutput } from "../shared/output-formatters.js";

export const toolStatsQueryTool: ToolDefinition = {
  name: "tool_stats_query",
  label: "查询工具使用统计",
  description:
    "查询 Agent 工具的使用统计信息，包括调用次数、成功率、平均耗时等。" +
    "支持按工具名过滤，按时间范围查询，生成统计报告。",

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("stats"),
      Type.Literal("report"),
      Type.Literal("export"),
      Type.Literal("cleanup")
    ], {
      description: "操作类型：stats=查询统计，report=生成报告，export=导出CSV，cleanup=清理旧数据"
    }),
    tool_name: Type.Optional(Type.String({
      description: "工具名称（可选），仅查询指定工具的统计"
    })),
    from_date: Type.Optional(Type.String({
      description: "起始日期（可选），格式: YYYY-MM-DD，仅统计此日期之后的数据"
    })),
    top_n: Type.Optional(Type.Integer({
      description: "报告中显示前N个工具（默认20）",
      minimum: 1,
      maximum: 100
    })),
    output_path: Type.Optional(Type.String({
      description: "导出CSV文件的路径（仅 action=export 时需要）"
    })),
    retention_days: Type.Optional(Type.Integer({
      description: "清理时保留的天数（仅 action=cleanup 时需要，默认30天）",
      minimum: 1,
      maximum: 365
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    const { action, tool_name, from_date, top_n = 20, output_path, retention_days = 30 } = params as {
      action: 'stats' | 'report' | 'export' | 'cleanup';
      tool_name?: string;
      from_date?: string;
      top_n?: number;
      output_path?: string;
      retention_days?: number;
    };
    const statsManager = getStatsManager();

    try {
      // 解析日期
      const fromDate = from_date ? new Date(from_date) : undefined;
      if (from_date && isNaN(fromDate!.getTime())) {
        return {
          content: [{ type: "text" as const, text: `错误：无效的日期格式 "${from_date}"，应为 YYYY-MM-DD` }],
          details: null
        };
      }

      switch (action) {
        case "stats": {
          // 查询统计
          const stats = statsManager.getStats(tool_name, fromDate);

          if (stats.length === 0) {
            return {
              content: [{ type: "text" as const, text: "暂无统计数据" }],
              details: null
            };
          }

          // 格式化为表格
          const output = formatTableOutput(
            stats,
            [
              { key: "toolName", label: "工具名称", width: 30 },
              { key: "totalCalls", label: "调用次数", width: 10, align: "right" },
              { key: "successRate", label: "成功率", width: 10, align: "right", format: (v) => `${v.toFixed(1)}%` },
              { key: "avgDuration", label: "平均耗时", width: 12, align: "right", format: (v) => `${v}ms` }
            ],
            {
              title: tool_name ? `工具统计: ${tool_name}` : "工具使用统计",
              maxRows: 50
            }
          );

          return {
            content: [{ type: "text" as const, text: output }],
            details: { stats }
          };
        }

        case "report": {
          // 生成报告
          const report = statsManager.generateReport({ topN: top_n, fromDate });

          return {
            content: [{ type: "text" as const, text: report }],
            details: null
          };
        }

        case "export": {
          // 导出CSV
          if (!output_path) {
            return {
              content: [{ type: "text" as const, text: "错误：导出CSV需要提供 output_path 参数" }],
              details: null
            };
          }

          statsManager.exportToCsv(output_path);

          return {
            content: [{ type: "text" as const, text: `✅ 统计数据已导出到: ${output_path}` }],
            details: null
          };
        }

        case "cleanup": {
          // 清理旧数据
          const removedCount = statsManager.cleanup(retention_days);

          return {
            content: [{
              type: "text" as const,
              text: `✅ 清理完成\n\n清理了 ${removedCount} 条超过 ${retention_days} 天的旧记录`
            }],
            details: { removedCount, retentionDays: retention_days }
          };
        }

        default:
          return {
            content: [{ type: "text" as const, text: `错误：未知的操作类型 "${action}"` }],
            details: null
          };
      }
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `❌ 统计查询失败\n\n错误: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: null
      };
    }
  }
};
