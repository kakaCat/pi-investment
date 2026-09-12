/**
 * PromptEvolverTool - 提示词进化工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { Context } from '@deepseek-ai/cordis';
import type { OsMemoryStore } from '../../index';
import { promptEvolverPrompt, PromptEvolverParams, PromptEvolverResult } from './prompt';
import { registerCandidate, readCandidates, type CandidateRecord } from '../../candidates';
import {
  assertNoDamage,
  extractRuleDefs,
  findDuplicateRuleDefs,
  normalizeRulesContent,
  type NormalizeResult,
} from '../../mergeSection';

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

    // 有界并发处理建议（3 路），避免多条建议串行 LLM 调用导致超时
    const CONCURRENCY = 3;
    const suggestions = params.suggestions;
    const processSuggestion = async (suggestion: any): Promise<{ proposal: any; result?: any }> => {
      try {
        // 1. 读取当前段落内容
        const currentContent = await this.readSection(suggestion.section);

        // 2. LLM 改写段落（失败时回退为确定性增量合并，不再裸拼接）
        const rewritten = await this.llmRewriteSection(
          suggestion.section,
          currentContent,
          suggestion
        );
        let content = rewritten.content;
        let method: string = rewritten.method;

        // 3. 落盘前归一化（2026-09-12 修复）
        //    背景：上游（daily_distill）会把「整段全文」当建议再喂回来，或携带
        //    [object Object] 损坏标记；LLM 整段重写因此常出现规则 ID 重复定义
        //    （实证 2026-09-12：rules 段 R-001…R-015 全量重复 → genome guard 拒绝，变异 0/1）。
        //    归一化策略：合法整段重写 → replace；含重复定义/删改既有 ID → 按当前段增量合并。
        let norm: NormalizeResult | null = null;
        const isRules = suggestion.section === 'rules' || extractRuleDefs(currentContent).length > 0;
        if (isRules) {
          assertNoDamage(String(suggestion.content ?? ''), '建议内容');
          assertNoDamage(content, `${suggestion.section} 候选内容`);
          norm = normalizeRulesContent(currentContent, content);
          if (norm.semantics === 'delta' && findDuplicateRuleDefs(content).length > 0) {
            method = method === 'llm' ? 'llm+dedup' : `${method}+dedup`;
          }
          if (norm.noop) {
            // LLM 输出不可用（无新增/与当前段等价）→ 退一步用原始建议内容做增量
            const alt = normalizeRulesContent(currentContent, String(suggestion.content ?? ''));
            if (!alt.noop) {
              norm = alt;
              method = `${method}+delta_from_suggestion`;
            }
          }
          content = norm.content;
          assertNoDamage(content, `${suggestion.section} 归一化结果`);
          const stillDup = findDuplicateRuleDefs(content);
          if (stillDup.length > 0) {
            throw new Error(`${suggestion.section} 归一化后仍存在重复规则定义：${stillDup.join(', ')}，拒绝写入基因组`);
          }
        } else {
          assertNoDamage(content, `${suggestion.section} 候选内容`);
        }

        // 4. 生成 diff 预览
        const diff = this.generateDiff(currentContent, content);

        const proposal = {
          section: suggestion.section,
          action: suggestion.type || 'update',
          method,
          content,
          reason: suggestion.reason,
          diff,
          // 增量语义（2026-09-12）：下游按 delta 沉淀，避免把整段当建议再次回灌
          added_ids: norm?.addedIds ?? [],
          dropped_rewrite_ids: norm?.droppedRewriteIds ?? [],
          deduped_ids: norm?.dedupedIds ?? [],
          delta: norm?.deltaText ?? '',
          semantics: norm?.semantics,
          noop: norm?.noop ?? false,
        };

        // 5. 如果非预览模式，调用 genome_update 应用为 candidate
        if (!dryRun) {
          if (norm?.noop) {
            return {
              proposal,
              result: {
                success: false,
                section: suggestion.section,
                message: '无实质变更：建议未包含新的规则 ID（rules 段只允许新增，不允许删改既有 ID），已拒绝应用以免生成空更新候选',
              },
            };
          }
          try {
            const updateResult = await this.callGenomeUpdate(
              suggestion.section,
              content,
              suggestion.reason,
              'candidate'
            );
            // ── 登记去重（2026-09-12，w-adb088f2）──────────────────────────────
            // genome_update 自 3d850ab5（2026-09-12 21:54）起，在 stage='candidate' 时
            // 自行登记 candidates.json 并回传 candidate_id。本处 2026-09-03 引入的补充登记
            // （当时 genome_update 尚不登记）遂成冗余：若不跳过会造成**同一次变异双登记**
            // —— 实证 cand_1789225325354_pc9f9k 与 cand_1789225325389_7sd9s8（相差 35ms，
            // 同 section_version/genome_version/baseline），验证门将对同一变更重复裁决。
            // 策略：优先采用 genome_update 的登记；仅在其未回传 candidate_id 时兜底自登记。
            const existingCandidateId = updateResult?.candidate_id
              ? String(updateResult.candidate_id)
              : '';
            if (existingCandidateId) {
              let observeUntil: string | undefined;
              try {
                // @ts-ignore ctx.genome 由 genome 插件注入，无类型声明
                const dir = this.ctx.genome?.genomeDir;
                if (dir) {
                  observeUntil = readCandidates(dir).find((r) => r.id === existingCandidateId)?.observe_until;
                }
              } catch {
                // 读取失败不影响主流程（仅观察期信息缺失）
              }
              return {
                proposal,
                result: {
                  success: true,
                  section: suggestion.section,
                  message: `已更新为 candidate 版本（登记由 genome_update 完成：${existingCandidateId}${
                    observeUntil ? `，观察期至 ${observeUntil}` : ''
                  }）`,
                  candidate_id: existingCandidateId,
                  observe_until: observeUntil,
                  stage: 'candidate' as const,
                },
              };
            }

            // ── 兜底登记（2026-09-03 引入）────────────────────────────────────
            // 仅当 genome_update 未回传 candidate_id（旧版 genome_update 只写
            // genome.json history、不登记 candidates.json → validation_gate 无案可裁）时执行。
            // baseline = 变更前一代（genome_version gN → g(N-1)，与历史实现 80ce5cfc 一致）
            let candidate: CandidateRecord | null = null;
            try {
              const gv = String(updateResult?.genome_version || '');
              const gm = gv.match(/^g(\d+)$/);
              const baselineVersion = gm ? `g${parseInt(gm[1], 10) - 1}` : gv;
              // @ts-ignore ctx.genome 由 genome 插件注入，无类型声明
              const genomeDir = this.ctx.genome?.genomeDir;
              if (!genomeDir) {
                throw new Error('ctx.genome.genomeDir 不可用，无法登记 candidate');
              }
              candidate = registerCandidate({
                genomeDir,
                section: suggestion.section,
                sectionVersion: updateResult?.new_version,
                genomeVersion: updateResult?.genome_version,
                baselineVersion,
                observeDays,
                mutationType: 'prompt',
              });
            } catch (regErr: any) {
              // 登记失败不阻断应用成功——但必须显式告警（静默失败是最坏的伪装）
              return {
                proposal,
                result: {
                  success: true,
                  section: suggestion.section,
                  message: `已更新为 candidate 版本（⚠️ candidate 登记失败: ${regErr.message}，验证门将无法裁决）`,
                  stage: 'candidate' as const,
                },
              };
            }
            return {
              proposal,
              result: {
                success: true,
                section: suggestion.section,
                message: `已更新为 candidate 版本并登记（${candidate.id}），观察期至 ${candidate.observe_until}`,
                candidate_id: candidate.id,
                observe_until: candidate.observe_until,
                stage: 'candidate' as const,
              },
            };
          } catch (e: any) {
            return {
              proposal,
              result: {
                success: false,
                section: suggestion.section,
                message: e.message,
              },
            };
          }
        }
        return { proposal };
      } catch (e: any) {
        return {
          proposal: {
            section: suggestion.section,
            action: 'error',
            method: 'failed',
            content: '',
            reason: e.message,
          },
        };
      }
    };

    // 按索引保序并发执行
    const indexed = suggestions.map((s, i) => ({ s, i }));
    for (let start = 0; start < indexed.length; start += CONCURRENCY) {
      const batch = indexed.slice(start, start + CONCURRENCY);
      const batchResults = await Promise.all(batch.map(({ s }) => processSuggestion(s)));
      batchResults.forEach((r, j) => {
        proposals[batch[j].i] = r.proposal;
        if (r.result) results[batch[j].i] = r.result;
      });
    }
    // 压缩空洞（失败建议的 proposal 已在 catch 中填充，results 可能有 undefined）
    const filledResults = results.filter(Boolean);

    const summary = dryRun
      ? `预览模式：生成 ${proposals.length} 条提案（未应用）`
      : `应用模式：${filledResults.filter(r => r.success).length}/${filledResults.length} 条成功应用`;

    return {
      proposals,
      summary,
      applied_count: filledResults.filter(r => r.success).length,
      results: dryRun ? [] : filledResults,
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

  /**
   * 覆盖 toDSHToolDefinition，使用简化的 parameters 定义
   */
  toDSHToolDefinition() {
    return {
      name: this.metadata.name,
      description: this.prompt.description,
      parameters: {
        suggestions: {
          type: 'array',
          description: 'experience_distill 输出的建议数组，每个建议包含 type/section/content/reason',
          required: true,
          items: { type: 'object', additionalProperties: true },
        },
        dry_run: {
          type: 'boolean',
          description: 'true（默认）：只生成预览，不执行；false：以 candidate 观察版应用（须经 validation_gate 裁决转正）',
        },
        observe_days: {
          type: 'number',
          description: 'candidate 观察期（天），默认 5',
        },
      },
      output: {
        schema: this.prompt.output?.schema || { type: 'object', additionalProperties: true },
        render: this.prompt.output?.render
          ?? ((_args: any, data: any) => [{ type: 'text', text: JSON.stringify(data, null, 2) }]),
      },
      timeoutMs: this.metadata.timeoutMs || 10000,
      execute: async (args: PromptEvolverParams) => {
        const response = await this.call(args);
        if (!response.success) {
          const err: any = response.error;
          const issue =
            typeof err === 'string' ? err
            : err?.issue ? err.issue
            : err?.error?.issue ? err.error.issue
            : '工具执行失败';
          throw new Error(issue);
        }
        return response.data;
      },
    } as any;
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
        `硬性约束：①只输出改写后的段落全文，不要任何解释、前言或代码块包裹；②总长度不超过 6000 字符；③禁止出现 {{ 或 }} 字符；④rules 段的规则 ID（R-xxx 标题）只允许新增，不允许删除或修改已有 ID；⑤不得与交易宪法冲突（9:30-15:00 交易时段、T+1、仓位上限、止损纪律）；⑥每个 R-xxx 标题行在输出中最多出现一次——已有规则原样保留其标题行，禁止重复输出。`,
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
      // 回退不再裸拼接（2026-09-12 修复）：rules 段改用确定性增量合并，
      // 既有规则以当前段为准、只追加候选里的新 ID；非 rules 段保持追加语义。
      if (section === 'rules' || extractRuleDefs(currentContent).length > 0) {
        const fallback = normalizeRulesContent(currentContent, String(suggestion.content || ''));
        return { content: fallback.content, method: 'append_fallback' };
      }
      return { content: currentContent.trim() + '\n' + (suggestion.content || '') + '\n', method: 'append_fallback' };
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
