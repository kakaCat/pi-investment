/**
 * Strategy Batch Validate Tool
 *
 * 批量验证策略有效性，对所有策略进行回测并评分
 *
 * 🆕 集成统一响应处理系统：大数据自动持久化
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { batchValidateStrategies } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface StrategyBatchValidateParams {
  startDate: string;
  endDate: string;
  threshold?: number;
  dryRun?: boolean;
}

export const strategyBatchValidateTool: ToolDefinition = {
  name: "strategy_batch_validate",
  label: "策略批量验证",
  description:
    "批量验证所有策略的有效性。" +
    "对每个策略进行回测，计算综合评分（年化收益、夏普比率、最大回撤、胜率、盈亏比）。" +
    "根据阈值筛选出有效策略，标记失效策略。" +
    "支持 dry-run 模式预览结果。" +
    "\n\n💾 大数据自动保存到本地文件。",

  parameters: Type.Object({
    startDate: Type.String({
      description: "回测开始日期，格式 YYYY-MM-DD（如 2024-05-27）"
    }),
    endDate: Type.String({
      description: "回测结束日期，格式 YYYY-MM-DD（如 2026-05-27）"
    }),
    threshold: Type.Optional(
      Type.Number({
        description: "评分阈值（0-100），低于此分数的策略标记为失败，默认 60"
      })
    ),
    dryRun: Type.Optional(
      Type.Boolean({
        description: "是否为预演模式（不更新数据库），默认 false"
      })
    )
  }),

  execute: async (_toolCallId, params: StrategyBatchValidateParams) => {
    const { startDate, endDate, threshold = 60, dryRun = false } = params;

    try {
      // 调用 v2 API 批量验证策略
      const result = await batchValidateStrategies({
        startDate,
        endDate,
        threshold,
        dryRun
      });

      if (!result.success) {
        return createErrorResponse(result.error || "未知错误");
      }

      // 使用统一响应处理（自动决定格式化或持久化）
      return handleToolResponse({
        toolName: 'strategy_batch_validate',
        data: result.data,
        formatter: (data) => _formatBatchValidation(data, startDate, endDate, threshold, dryRun),
        metadata: {
          startDate,
          endDate,
          threshold,
          dryRun,
          total: result.data.total,
          passed: result.data.passed,
          failed: result.data.failed,
        },
        threshold: 100 * 1024, // 100KB，批量验证数据通常很大
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  }
};

/**
 * 格式化批量验证结果
 */
function _formatBatchValidation(
  data: any,
  startDate: string,
  endDate: string,
  threshold: number,
  dryRun: boolean
): string {
  const failedStrategies = data.details.filter((d: any) => d.status === 'failed');
  const passedStrategies = data.details.filter((d: any) => d.status === 'passed');

  let output = `# 策略批量验证报告\n\n`;
  output += `**验证周期**: ${startDate} 至 ${endDate}\n`;
  output += `**评分阈值**: ${threshold}\n`;
  output += `**执行时长**: ${data.duration}秒\n`;
  output += `${dryRun ? '**模式**: 预演模式（未更新数据库）\n' : ''}\n`;
  output += `## 汇总统计\n\n`;
  output += `- 总数: ${data.total}\n`;
  output += `- 通过: ${data.passed}\n`;
  output += `- 失败: ${data.failed}\n\n`;

  if (failedStrategies.length > 0) {
    output += `## 失败策略列表\n\n`;
    failedStrategies.forEach((s: any) => {
      output += `### ${s.strategyName} (ID: ${s.strategyId})\n`;
      output += `- **评分**: ${s.score.toFixed(1)}\n`;
      output += `- **年化收益**: ${(s.metrics.annualReturn * 100).toFixed(2)}%\n`;
      output += `- **夏普比率**: ${s.metrics.sharpeRatio.toFixed(2)}\n`;
      output += `- **最大回撤**: ${(s.metrics.maxDrawdown * 100).toFixed(2)}%\n`;
      output += `- **胜率**: ${(s.metrics.winRate * 100).toFixed(2)}%\n`;
      output += `- **盈亏比**: ${s.metrics.profitFactor.toFixed(2)}\n`;
      output += `- **回测次数**: ${s.backtestCount}\n`;
      output += `- **错误次数**: ${s.errorCount}\n\n`;
    });
  }

  if (passedStrategies.length > 0) {
    output += `## 通过策略 Top 5\n\n`;
    const top5 = passedStrategies
      .sort((a: any, b: any) => b.score - a.score)
      .slice(0, 5);

    top5.forEach((s: any, idx: number) => {
      output += `### ${idx + 1}. ${s.strategyName} (ID: ${s.strategyId})\n`;
      output += `- **评分**: ${s.score.toFixed(1)}\n`;
      output += `- **年化收益**: ${(s.metrics.annualReturn * 100).toFixed(2)}%\n`;
      output += `- **夏普比率**: ${s.metrics.sharpeRatio.toFixed(2)}\n`;
      output += `- **最大回撤**: ${(s.metrics.maxDrawdown * 100).toFixed(2)}%\n`;
      output += `- **胜率**: ${(s.metrics.winRate * 100).toFixed(2)}%\n`;
      output += `- **盈亏比**: ${s.metrics.profitFactor.toFixed(2)}\n\n`;
    });
  }

  return output;
}
