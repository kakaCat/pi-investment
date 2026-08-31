/**
 * PromptEvolverTool - 提示词进化工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { Context } from '@deepseek-ai/cordis';
import type { OsMemoryStore } from '../../index';
import { promptEvolverPrompt, PromptEvolverParams, PromptEvolverResult } from './prompt';

/**
 * 提示词进化工具类
 *
 * 接收 experience_distill 建议，使用 LLM 改写段落，调用 genome_update 应用为 candidate 版本
 */
export class PromptEvolverTool extends BaseTool<PromptEvolverParams, PromptEvolverResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'prompt_evolver',
    category: 'evolver',
    version: '1.0.0',
    timeoutMs: 60000, // 60s（LLM 改写可能较慢）
  };

  protected readonly prompt = promptEvolverPrompt;

  constructor(
    private ctx: Context,
    private osMemory: OsMemoryStore,
    private llmProvider: string,
    private llmModel: string,
    private observeDays: number
  ) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(params: PromptEvolverParams): ValidationResult {
    // suggestions 必须是数组
    if (!Array.isArray(params.suggestions)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'suggestions',
        issue: 'suggestions 必须是数组',
        received: typeof params.suggestions,
        expected: 'array',
      };
    }

    // suggestions 不能为空
    if (params.suggestions.length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'suggestions',
        issue: 'suggestions 数组不能为空',
        received: '[]',
        expected: '至少包含一个建议',
      };
    }

    // 验证每个 suggestion 的结构
    for (let i = 0; i < params.suggestions.length; i++) {
      const s = params.suggestions[i];
      if (!s.section || typeof s.section !== 'string') {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: `suggestions[${i}].section`,
          issue: 'section 字段必须是非空字符串',
          received: s.section,
          expected: 'string',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(params: PromptEvolverParams, context: ToolContext): Promise<PromptEvolverResult> {
    const dryRun = params.dry_run !== false; // 默认 true
    const observeDays = params.observe_days || this.observeDays;
    const proposals: PromptEvolverResult['proposals'] = [];
    const results: PromptEvolverResult['results'] = [];

    for (const suggestion of params.suggestions) {
      try {
        // 1. 读取当前段落内容
        const currentContent = await this.readSection(suggestion.section);

        // 2. LLM 改写段落（失败时回退追加）
        const { content, method } = await this.llmRewriteSection(
          suggestion.section,
          currentContent,
          suggestion
        );

        // 3. 生成 diff 预览
        const diff = this.generateDiff(currentContent, content);

        proposals.push({
          section: suggestion.section,
          action: suggestion.type || 'update',
          method,
          content,
          reason: suggestion.reason,
          diff,
        });

        // 4. 如果非预览模式，调用 genome_update 应用为 candidate
        if (!dryRun) {
          try {
            await this.callGenomeUpdate(
              suggestion.section,
              content,
              suggestion.reason,
              'candidate'
            );
            results.push({
              success: true,
              section: suggestion.section,
              message: `已更新为 candidate 版本，观察期 ${observeDays} 天`,
            });
          } catch (e: any) {
            results.push({
              success: false,
              section: suggestion.section,
              message: e.message,
            });
          }
        }
      } catch (e: any) {
        proposals.push({
          section: suggestion.section,
          action: 'error',
          method: 'failed',
          content: '',
          reason: e.message,
        });
      }
    }

    const summary = dryRun
      ? `预览模式：生成 ${proposals.length} 条提案（未应用）`
      : `应用模式：${results.filter(r => r.success).length}/${results.length} 条成功应用`;

    return {
      proposals,
      summary,
      applied_count: results.filter(r => r.success).length,
      results: dryRun ? [] : results,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: PromptEvolverResult, context: ToolContext): ToolResponse<PromptEvolverResult> {
    return {
      success: true,
      data: result,
    };
  }

  // ===== 私有辅助方法 =====

  /**
   * LLM 段落改写
   */
  private async llmRewriteSection(
    section: string,
    currentContent: string,
    suggestion: any
  ): Promise<{ content: string; method: 'llm' | 'append_fallback' }> {
    try {
      const prompt = [
        `你是投资 Agent 的提示词进化器。下面是 Agent 系统提示词中「${section}」段的当前全文，以及一条来自经验蒸馏的改进建议。`,
        `请整体改写该段：把建议自然地融入（新增/强化/淘汰相应内容），保持 markdown 结构清晰、语言精炼。`,
        `硬性约束：①只输出改写后的段落全文，不要任何解释、前言或代码块包裹；②总长度不超过 6000 字符；③禁止出现 {{ 或 }} 字符；④rules 段的规则 ID（R-xxx 标题）只允许新增，不允许删除或修改已有 ID；⑤不得与交易宪法冲突（9:30-15:00 交易时段、T+1、仓位上限、止损纪律）。`,
        ``,
        `【当前段落全文】`,
        currentContent,
        ``,
        `【改进建议】`,
        `理由：${suggestion.reason || '经验蒸馏'}`,
        `内容：${suggestion.content || ''}`,
      ].join('\n');

      let text = '';
      for await (const chunk of (this.ctx as any).llm.stream({
        provider: this.llmProvider,
        model: this.llmModel,
        maxTokens: 4000,
        messages: [{
          role: 'user',
          content: [{ type: 'text', text: prompt }],
          source: { kind: 'plugin', plugin: 'evolver' },
        }],
        signal: new AbortController().signal,
      })) {
        if (chunk?.type === 'text-delta') text += (chunk.text ?? chunk.delta ?? '');
      }

      const cleaned = text.replace(/^```(?:markdown|md)?\s*\n?/i, '').replace(/\n?```\s*$/i, '').trim();
      if (cleaned.length < 50 || cleaned.length > 7800) {
        throw new Error(`LLM 输出长度异常（${cleaned.length} 字符），回退追加模式`);
      }
      return { content: cleaned + '\n', method: 'llm' };
    } catch (e: any) {
      return { content: currentContent.trim() + '\n' + (suggestion.content || ''), method: 'append_fallback' };
    }
  }

  /**
   * 读取段内容
   */
  private async readSection(sectionName: string): Promise<string> {
    const fs = await import('fs');
    const path = await import('path');
    // @ts-ignore
    const genomeDir = this.ctx.genome.genomeDir;
    const filePath = path.join(genomeDir, 'sections', `${sectionName}.md`);

    if (!fs.existsSync(filePath)) {
      throw new Error(`Section file not found: ${sectionName}.md`);
    }

    return fs.readFileSync(filePath, 'utf-8');
  }

  /**
   * 生成简单的 diff 预览
   */
  private generateDiff(oldContent: string, newContent: string): string {
    const oldLines = oldContent.split('\n');
    const newLines = newContent.split('\n');
    const added = newLines.filter(line => !oldLines.includes(line));

    if (added.length === 0) {
      return '(无变化)';
    }

    return added.map(line => `+ ${line}`).join('\n');
  }

  /**
   * 调用 genome_update 工具
   */
  private async callGenomeUpdate(
    section: string,
    content: string,
    reason: string,
    stage: 'active' | 'candidate' = 'active'
  ): Promise<any> {
    const result = await (this.ctx.tools as any).execute({
      name: 'genome_update',
      arguments: { section, content, reason, stage, force: false },
      signal: new AbortController().signal,
    });
    if (result?.isError) {
      throw new Error(result?.error?.message || 'genome_update 调用失败');
    }
    return result?.value ?? result;
  }
}
