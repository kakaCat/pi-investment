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

    // 1. 调用 learning_analyze 分析经验库（生成改进建议）
    const distillResult = await this.callTool('learning_analyze', {
      scope: 'recent',
      focus: 'all',
      min_samples: Math.max(1, Math.min(days, 30)),
    });

    // 2. 提取建议（learning_analyze 输出 suggestions: string[]，需转换为 prompt_evolver 建议格式）
    //    限 3 条：避免一次过多 LLM 改写调用导致超时
    const rawSuggestions: string[] = (distillResult?.suggestions || []).slice(0, 3);
    const suggestions = rawSuggestions.map((s: string) => ({
      type: 'strengthen',
      section: 'rules',
      content: s,
      reason: 'learning_analyze 自动蒸馏',
    }));

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
        genome_version: distillResult.genome_version || 'current',
        period: distillResult.period || { from: '', to: '' },
        stats: distillResult.stats || {
          total_experiences: distillResult?.sample_count ?? 0,
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
   * 生成每日蒸馏摘要（适配 learning_analyze 输出：patterns/suggestions/sample_count）
   */
  private generateSummary(distillResult: any, evolverResult: any, autoApply: boolean): string {
    const patterns = distillResult?.patterns || [];
    const suggestions = distillResult?.suggestions || [];
    const sampleCount = distillResult?.sample_count ?? 0;
    const proposals = evolverResult?.proposals || [];

    let summary = `📊 每日蒸馏报告\n\n`;
    summary += `- 分析样本数: ${sampleCount}\n`;
    summary += `- 发现模式: ${patterns.length} 个\n`;
    summary += `- 蒸馏建议: ${suggestions.length} 条\n\n`;

    if (patterns.length > 0) {
      summary += `模式摘要:\n`;
      patterns.slice(0, 5).forEach((p: any, i: number) => {
        summary += `${i + 1}. ${p?.description ?? p?.pattern ?? JSON.stringify(p)}\n`;
      });
      summary += `\n`;
    }

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
