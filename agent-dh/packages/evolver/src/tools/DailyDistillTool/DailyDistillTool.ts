/**
 * DailyDistillTool - 每日蒸馏编排工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { Context } from '@deepseek-ai/cordis';
import type { OsMemoryStore } from '../../index';
import { dailyDistillPrompt, DailyDistillParams, DailyDistillResult } from './prompt';

/**
 * 每日蒸馏编排工具类
 *
 * 编排完整蒸馏流程：experience_distill → prompt_evolver
 */
export class DailyDistillTool extends BaseTool<DailyDistillParams, DailyDistillResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'daily_distill',
    category: 'evolver',
    version: '1.0.0',
    timeoutMs: 180000, // 180s（完整蒸馏流程可能较慢）
  };

  protected readonly prompt = dailyDistillPrompt;

  constructor(
    private ctx: Context,
    private osMemory: OsMemoryStore
  ) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(params: DailyDistillParams): ValidationResult {
    if (params.days !== undefined) {
      if (typeof params.days !== 'number' || params.days < 1 || params.days > 90) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'days',
          issue: 'days 必须在 1-90 之间',
          received: params.days,
          expected: '1 <= days <= 90',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(params: DailyDistillParams, context: ToolContext): Promise<DailyDistillResult> {
    const days = params.days || 7;
    const autoApply = params.auto_apply || false;

    // 1. 调用 experience_distill 蒸馏经验
    const distillResult = await this.callTool('experience_distill', {
      days,
    });

    // 2. 提取建议
    const suggestions = distillResult?.suggestions || [];

    // 3. 调用 prompt_evolver 生成/应用提案
    const evolverResult = suggestions.length > 0
      ? await this.callTool('prompt_evolver', {
          suggestions,
          dry_run: !autoApply,
        })
      : { proposals: [], summary: '无改进建议', applied_count: 0, results: [] };

    // 4. 生成总结
    const summary = this.generateSummary(distillResult, evolverResult, autoApply);

    return {
      distill_summary: {
        genome_version: distillResult.genome_version || 'unknown',
        period: distillResult.period || { from: '', to: '' },
        stats: distillResult.stats || {
          total_experiences: 0,
          avg_reward: 0,
          success_rate: 0,
        },
      },
      evolver_result: {
        proposals: evolverResult.proposals || [],
        summary: evolverResult.summary || '',
        applied_count: evolverResult.applied_count || 0,
      },
      summary,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: DailyDistillResult, context: ToolContext): ToolResponse<DailyDistillResult> {
    return {
      success: true,
      data: result,
    };
  }

  // ===== 私有辅助方法 =====

  /**
   * 调用其他工具
   */
  private async callTool(name: string, args: Record<string, any>): Promise<any> {
    const result = await (this.ctx.tools as any).execute({
      name,
      arguments: args,
      signal: new AbortController().signal,
    });
    if (result?.isError) {
      throw new Error(result?.error?.message || `${name} 调用失败`);
    }
    return result?.value ?? result;
  }

  /**
   * 生成每日蒸馏摘要
   */
  private generateSummary(distillResult: any, evolverResult: any, autoApply: boolean): string {
    const stats = distillResult.stats || {};
    const proposals = evolverResult.proposals || [];

    let summary = `📊 每日蒸馏报告\n\n`;
    summary += `基因组版本: ${distillResult.genome_version}\n`;
    summary += `分析周期: ${distillResult.period?.from?.slice(0, 10)} ~ ${distillResult.period?.to?.slice(0, 10)}\n\n`;
    summary += `统计:\n`;
    summary += `- 总经验数: ${stats.total_experiences}\n`;
    summary += `- 平均奖励: ${stats.avg_reward}\n`;
    summary += `- 成功率: ${(stats.success_rate * 100).toFixed(1)}%\n\n`;

    if (proposals.length > 0) {
      summary += `生成 ${proposals.length} 条改进提案:\n`;
      proposals.forEach((p: any, i: number) => {
        summary += `${i + 1}. ${p.section} (${p.action}): ${p.reason}\n`;
      });
      summary += `\n`;
    }

    if (autoApply) {
      const appliedCount = evolverResult.applied_count || 0;
      summary += `✅ 已应用: ${appliedCount}/${proposals.length} 条改进\n`;
    } else {
      summary += `⚠️  预览模式: 未实际应用改进（传 auto_apply=true 自动应用）\n`;
    }

    return summary;
  }
}
