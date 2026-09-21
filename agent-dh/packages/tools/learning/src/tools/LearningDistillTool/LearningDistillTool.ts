/**
 * LearningDistillTool - 规则提炼工具
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { learningDistillPrompt, LearningDistillParams, LearningDistillResult } from './prompt';

export class LearningDistillTool extends BaseTool<LearningDistillParams, LearningDistillResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'learning_distill',
    category: 'learning',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = learningDistillPrompt;

  constructor(
    private loadExperiencesBySource: (source: string) => Promise<any[]>,
    private distillRules: (options: any) => any[],
    private getDistillMethod: (format: string) => string,
    private validateRules: (rules: any[], experiences: any[]) => Record<string, any>,
    // 2026-09-03 Fix③：规则落库回调（把蒸馏规则持久化为 kind='rule' status='testing' 候选）。
    // learning_apply 需要一个真实存在的规则对象来执行"转正/应用"，distill 是唯一写入方。
    private persistRules?: (rules: any[], meta: { source: string; target_format: string }) => Promise<any[]>
  ) {
    super();
  }

  protected validate(args: LearningDistillParams): ValidationResult {
    const validFormats = ['rule', 'prompt', 'code'];
    if (!args.target_format || !validFormats.includes(args.target_format)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'target_format',
          issue: `target_format 必须是: ${validFormats.join(', ')}`,
          expected: validFormats.join(' | '),
        },
      };
    }

    if (!args.source) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'source',
          issue: 'source 是必需的',
          expected: 'string',
        },
      };
    }

    return { success: true };
  }

  protected async execute(args: LearningDistillParams, _context: ToolContext): Promise<LearningDistillResult> {
    const experiences = await this.loadExperiencesBySource(args.source);

    const rules = this.distillRules({
      experiences,
      targetFormat: args.target_format,
      minConfidence: args.min_confidence || 0.6,
      maxRules: args.max_rules || 10,
    });

    // 2026-09-03 Fix③：蒸馏产出规则即落库为 kind='rule' status='testing' 候选，
    // 使 learning_apply 有真实可转正对象（rules 项带回 memory_id 供后续引用）。
    let finalRules = rules;
    let persistedCount = 0;
    let persistError: string | null = null;
    if (this.persistRules && rules.length > 0) {
      try {
        finalRules = await this.persistRules(rules, {
          source: args.source,
          target_format: args.target_format,
        });
        persistedCount = finalRules.filter((r: any) => r.memory_id).length;
      } catch (e: any) {
        // 落库失败不吞：规则仍返回（纯计算产物），但显式标记持久化失败供调用方识别，
        // 避免"静默失败伪装成功"——learning_apply 会因此诚实返回"规则不存在"。
        persistError = String(e?.message || e);
      }
    }

    // 2026-08-30 修复：in-process 学习服务的规则/统计字段可能含 undefined/NaN，
    // 直接返回会触发 DSH lossless JSON 校验失败。统一递归清洗。
    return sanitizeLossless({
      success: true,
      rules: finalRules,
      source_count: experiences.length,
      distill_method: this.getDistillMethod(args.target_format),
      validation_stats: this.validateRules(finalRules, experiences),
      persistence: rules.length > 0
        ? { persisted: persistedCount, total: rules.length, failed: rules.length - persistedCount, error: persistError }
        : undefined,
    });
  }

  protected wrap(result: LearningDistillResult): ToolResponse<LearningDistillResult> {
    return { success: true, data: result };
  }
}
