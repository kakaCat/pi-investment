/**
 * Evolver Plugin - Prompt Evolution Engine
 * P1-2: 接收 experience_distill 建议，生成段更新提案，调用 genome_update 应用
 * P2 (RFC 008): 验证门——提案应用为 candidate 观察版，观察期后裁决转正/回滚
 */
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import * as fs from 'fs';
import * as path from 'path';

/** 观察期候选记录（RFC 008 §3.3） */
interface CandidateRecord {
  id: string;
  section: string;
  section_version: number;
  genome_version: string;
  baseline_version: string;
  created_at: string;
  observe_until: string;
  status: 'watching' | 'promoted' | 'rejected';
  note?: string;
}

export default class EvolverPlugin extends Service {
  static inject = ['tools', 'genome'];  // 依赖 genome 插件

  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
    }).default({} as any),
    observeDays: z.number().default(5),  // 模拟盘观察期（交易日）
  }).default({} as any);

  private qv2: QuantsysV2Client;
  private observeDays: number;

  constructor(ctx: Context, config: any) {
    super(ctx, 'evolver');
    this.qv2 = new QuantsysV2Client({ baseURL: config?.quantsysV2?.baseURL || 'http://localhost:5001' });
    this.observeDays = config?.observeDays || 5;
    this.registerTools();
  }

  // ============ RFC 008: candidates 持久化（genomeDir/candidates.json） ============

  private get candidatesPath(): string {
    // @ts-ignore - genome 插件运行时字段
    return path.join(this.ctx.genome.genomeDir, 'candidates.json');
  }

  private readCandidates(): CandidateRecord[] {
    try {
      if (!fs.existsSync(this.candidatesPath)) return [];
      return JSON.parse(fs.readFileSync(this.candidatesPath, 'utf-8'));
    } catch { return []; }
  }

  private writeCandidates(list: CandidateRecord[]): void {
    const tmp = this.candidatesPath + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(list, null, 2));
    fs.renameSync(tmp, this.candidatesPath);
  }

  private registerCandidate(section: string, sectionVersion: number, genomeVersion: string, baselineVersion: string, observeDays?: number): CandidateRecord {
    const days = observeDays || this.observeDays;
    const now = new Date();
    const rec: CandidateRecord = {
      id: `cand_${Date.now()}`,
      section,
      section_version: sectionVersion,
      genome_version: genomeVersion,
      baseline_version: baselineVersion,
      created_at: now.toISOString(),
      observe_until: new Date(now.getTime() + days * 86400000).toISOString(),
      status: 'watching',
    };
    const list = this.readCandidates();
    list.push(rec);
    this.writeCandidates(list);
    return rec;
  }

  /** 从记忆库取某基因组代数的打标经验奖励（P0-3 打标的消费端） */
  private async searchRewards(genomeVersion: string): Promise<{ count: number; avg: number }> {
    try {
      const res = await this.qv2.searchMemory({ q: `genome:${genomeVersion}`, kind: 'experience', limit: 50 });
      const items = res?.items || [];
      const rewards: number[] = [];
      for (const it of items) {
        try {
          const content = typeof it.content === 'string' ? JSON.parse(it.content) : it.content;
          if (typeof content?.reward === 'number') rewards.push(content.reward);
        } catch { /* 单条解析失败跳过 */ }
      }
      return { count: rewards.length, avg: rewards.length ? rewards.reduce((a, b) => a + b, 0) / rewards.length : 0 };
    } catch { return { count: 0, avg: 0 }; }
  }

  /**
   * 跨工具调用（2026-08-20 验收修复）：ToolRuntime 没有 list() 方法，
   * 程序内调用的正确入口是 ctx.tools.execute({name, arguments, signal})，
   * 会走完整流水线（pre-execute 门禁 + post-execute 瀑布），
   * 返回值取 result.value（工具原始返回）。
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
   * RFC 008 §2.2 裁决逻辑：观察期到期的 candidate 对比基准期打标经验
   * - 证据不足（candidate 样本 < minSamples）→ 延期 2 天
   * - 平均奖励显著低于基准（差值 > 0.1）→ genome_rollback + 标记 rejected
   * - 否则 → genome_promote 转正 + 标记 promoted
   * force=true 跳过时间与样本数门槛（验收/人工裁决用）
   */
  private async judgeCandidates(force: boolean, minSamples = 3): Promise<any[]> {
    const list = this.readCandidates();
    const now = Date.now();
    const verdicts: any[] = [];

    for (const c of list.filter(x => x.status === 'watching')) {
      const expired = now >= Date.parse(c.observe_until);
      if (!expired && !force) {
        verdicts.push({ id: c.id, section: c.section, genome_version: c.genome_version, verdict: 'watching', observe_until: c.observe_until });
        continue;
      }

      const [cand, base] = await Promise.all([
        this.searchRewards(c.genome_version),
        this.searchRewards(c.baseline_version),
      ]);

      if (!force && cand.count < minSamples) {
        c.observe_until = new Date(now + 2 * 86400000).toISOString();
        c.note = `证据不足延期（candidate 样本 ${cand.count} < ${minSamples}）`;
        verdicts.push({ id: c.id, section: c.section, verdict: 'extended', cand_samples: cand.count, note: c.note });
        continue;
      }

      const drop = base.avg - cand.avg;
      if (drop > 0.1) {
        // 显著恶化 → 回滚到 candidate 之前的段版本
        try {
          await this.callTool('genome_rollback', { section: c.section, to_section_version: c.section_version - 1, reason: `验证门裁决：candidate 平均奖励 ${cand.avg.toFixed(3)} 显著低于基准 ${base.avg.toFixed(3)}（样本 ${cand.count}/${base.count}）` });
          c.status = 'rejected';
          verdicts.push({ id: c.id, section: c.section, verdict: 'rejected', cand_avg: cand.avg, base_avg: base.avg, rolled_back_to: c.section_version - 1 });
        } catch (e: any) {
          verdicts.push({ id: c.id, section: c.section, verdict: 'reject_failed', error: e.message });
        }
      } else {
        try {
          await this.callTool('genome_promote', { section: c.section, reason: `观察期达标：candidate 平均奖励 ${cand.avg.toFixed(3)} vs 基准 ${base.avg.toFixed(3)}（样本 ${cand.count}/${base.count}）` });
          c.status = 'promoted';
          verdicts.push({ id: c.id, section: c.section, verdict: 'promoted', cand_avg: cand.avg, base_avg: base.avg });
        } catch (e: any) {
          verdicts.push({ id: c.id, section: c.section, verdict: 'promote_failed', error: e.message });
        }
      }
    }

    this.writeCandidates(list);
    return verdicts;
  }

  private registerTools(): void {
    // P1-2: prompt_evolver - 提示词进化工具
    this.ctx.tools.register(defineTool({
      name: 'prompt_evolver',
      description: 'P1-2 提示词进化：接收 distill 建议，生成段更新提案，调用 genome_update 应用。用于：每日蒸馏、手动应用改进、A/B 测试新规则。',
      parameters: {
        suggestions: {
          type: 'array',
          description: 'experience_distill 输出的建议数组',
          items: {
            type: 'object',
            properties: {
              type: { type: 'string' },
              section: { type: 'string' },
              content: { type: 'string' },
              reason: { type: 'string' },
            },
            additionalProperties: true,
          },
          required: true,
        },
        dry_run: {
          type: 'boolean',
          description: 'true（默认）：只生成预览，不执行；false：以 candidate 观察版应用（须经 validation_gate 裁决转正）',
          default: true,
        },
        observe_days: {
          type: 'number',
          description: 'candidate 观察期（天），默认 5',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            proposals: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  section: { type: 'string' },
                  action: { type: 'string' },
                  content: { type: 'string' },
                  reason: { type: 'string' },
                  preview_diff: { type: 'string' },
                },
                additionalProperties: false,
              },
            },
            applied: { type: 'boolean' },
            results: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: true,
              },
            },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: JSON.stringify(value, null, 2) },
        ],
      },
      timeoutMs: 60000,
      execute: async (args: any) => {
        const { suggestions, dry_run } = args;
        const proposals = [];
        const results = [];

        // @ts-ignore
        const genome = this.ctx.genome;
        if (!genome || !genome.genomeData) {
          throw new Error('Genome plugin not available');
        }

        // 解析每条建议，生成提案
        for (const suggestion of suggestions) {
          if (suggestion.type === 'info') {
            continue;  // 跳过信息性建议
          }

          const section = suggestion.section;
          if (!section || !genome.genomeData.sections[section]) {
            continue;  // 跳过无效段
          }

          // 读取当前段内容
          const currentContent = await this.readSection(section);
          let newContent = currentContent;
          let action = 'modify';

          // 根据 type 生成新内容
          if (suggestion.type === 'add_rule') {
            // 追加规则到 rules 段
            newContent = currentContent.trim() + '\n' + suggestion.content;
            action = 'add';
          } else if (suggestion.type === 'modify_principle') {
            // 修改 principles（简化：追加到末尾）
            newContent = currentContent.trim() + '\n' + suggestion.content;
            action = 'modify';
          }

          // 生成 diff 预览
          const preview_diff = this.generateDiff(currentContent, newContent);

          const proposal = {
            section,
            action,
            content: newContent,
            reason: suggestion.reason || '经验蒸馏建议',
            preview_diff,
          };

          proposals.push(proposal);

          // 如果非 dry_run，执行 genome_update（RFC 008：以 candidate 观察版应用 + 登记观察）
          if (!dry_run) {
            try {
              const updateResult = await this.callGenomeUpdate(
                section,
                newContent,
                suggestion.reason || '经验蒸馏建议',
                'candidate'
              );
              // baseline = 变更前一代（新代数 -1），与 genome history 条目的 baseline_version 一致
              const gm = String(updateResult.genome_version).match(/^g(\d+)$/);
              const baselineVersion = gm ? `g${parseInt(gm[1], 10) - 1}` : updateResult.genome_version;
              const candidate = this.registerCandidate(
                section,
                updateResult.section_version,
                updateResult.genome_version,
                baselineVersion,
                args.observe_days
              );
              results.push({
                section,
                success: true,
                result: updateResult,
                candidate_id: candidate.id,
                observe_until: candidate.observe_until,
                stage: 'candidate',
              });
            } catch (error: any) {
              results.push({
                section,
                success: false,
                error: error.message,
              });
            }
          }
        }

        return {
          proposals,
          applied: !dry_run,
          results: dry_run ? [] : results,
        } as any;
      },
    } as any));

    // P1-3: daily_distill - 每日蒸馏编排（experience_distill → prompt_evolver）
    this.ctx.tools.register(defineTool({
      name: 'daily_distill',
      description: 'P1-3 每日蒸馏编排：自动执行 experience_distill → prompt_evolver → 通知。用于：盘后自动化、手动触发完整蒸馏流程。推荐每日 16:00 执行。',
      parameters: {
        days: {
          type: 'number',
          description: '分析最近 N 天经验（默认 7）',
          default: 7,
        },
        auto_apply: {
          type: 'boolean',
          description: 'true：自动应用改进（调用 genome_update）；false（默认）：只生成预览',
          default: false,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            distill_result: {
              type: 'object',
              additionalProperties: true,
            },
            evolver_result: {
              type: 'object',
              additionalProperties: true,
            },
            adjudication: {
              type: 'array',
              description: 'RFC 008 验证门裁决结果（转正/回滚/延期/观察中）',
              items: { type: 'object', additionalProperties: true },
            },
            summary: { type: 'string' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: value.summary },
        ],
      },
      timeoutMs: 120000,
      execute: async (args: any) => {
        const { days, auto_apply } = args;

        // Step 0（RFC 008）：先裁决到期的观察期候选（转正/回滚/延期）
        const adjudication = await this.judgeCandidates(false);

        // Step 1: experience_distill
        const distillTool = this.ctx.tools.list().find(t => t.name === 'experience_distill');
        if (!distillTool) {
          throw new Error('experience_distill tool not found');
        }

        // @ts-ignore
        const distillResult = await distillTool.execute({ days });

        // Step 2: prompt_evolver
        const evolverTool = this.ctx.tools.list().find(t => t.name === 'prompt_evolver');
        if (!evolverTool) {
          throw new Error('prompt_evolver tool not found');
        }

        const suggestions = distillResult.suggestions || [];
        // @ts-ignore
        const evolverResult = await evolverTool.execute({
          suggestions,
          dry_run: !auto_apply,
        });

        // Step 3: 生成摘要
        const summary = this.generateDistillSummary(distillResult, evolverResult, auto_apply);

        // Step 4: 写入 memory（记录蒸馏历史）
        const memoryTool = this.ctx.tools.list().find(t => t.name === 'memory_write');
        if (memoryTool) {
          try {
            // @ts-ignore
            await memoryTool.execute({
              content: `每日蒸馏 ${new Date().toISOString()}: ${summary}`,
              namespace: 'decision',
              importance: 0.8,
              tags: ['daily_distill', 'genome_evolution'],
            });
          } catch (e) {
            // 非关键操作，失败不影响主流程
          }
        }

        return {
          distill_result: distillResult,
          evolver_result: evolverResult,
          adjudication,
          summary,
        } as any;
      },
    } as any));

    // P2-1: candidate_status - 查询观察期候选（RFC 008 §3.2）
    this.ctx.tools.register(defineTool({
      name: 'candidate_status',
      description: '列出基因组观察期候选（candidate）：版本、剩余观察天数、对比基准、当前状态。用于：盘后例程检查验证门进度、人工审查进化队列。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          properties: {
            watching: { type: 'array', items: { type: 'object', additionalProperties: true } },
            settled: { type: 'array', items: { type: 'object', additionalProperties: true } },
            total: { type: 'number' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 10000,
      execute: async () => {
        const list = this.readCandidates();
        const now = Date.now();
        const watching = list.filter(c => c.status === 'watching').map(c => ({
          ...c,
          days_left: Math.max(0, Math.ceil((Date.parse(c.observe_until) - now) / 86400000)),
          expired: now >= Date.parse(c.observe_until),
        }));
        const settled = list.filter(c => c.status !== 'watching');
        return { watching, settled, total: list.length } as any;
      },
    } as any));

    // P2-2: validation_gate - 验证门裁决（RFC 008 核心工具）
    this.ctx.tools.register(defineTool({
      name: 'validation_gate',
      description: '验证门裁决：对观察期到期的基因组 candidate 对比基准期打标经验（平均奖励/样本数），达标转正（genome_promote）、显著恶化回滚（genome_rollback）、证据不足延期。force=true 跳过时间与样本门槛（验收/人工裁决用）。回测门（三区间回测）待策略参数纳入基因组后启用。',
      parameters: {
        action: {
          type: 'string',
          description: 'judge：裁决到期候选',
          enum: ['judge'],
          required: true,
        },
        force: {
          type: 'boolean',
          description: 'true：跳过观察期时间与最小样本数门槛（验收/人工裁决用）',
          default: false,
        },
        min_samples: {
          type: 'number',
          description: '裁决所需 candidate 期最小样本数，默认 3',
          default: 3,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            verdicts: { type: 'array', items: { type: 'object', additionalProperties: true } },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 60000,
      execute: async (args: any) => {
        const verdicts = await this.judgeCandidates(args.force || false, args.min_samples || 3);
        return { verdicts } as any;
      },
    } as any));
  }

  /**
   * 读取段内容
   */
  private async readSection(sectionName: string): Promise<string> {
    // @ts-ignore
    const genome = this.ctx.genome;
    const fs = await import('fs');
    const path = await import('path');
    
    const genomeDir = genome.genomeDir;
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
   * stage='candidate' 时新版本标记为观察版（RFC 008），需 validation_gate 裁决转正
   */
  private async callGenomeUpdate(
    section: string,
    content: string,
    reason: string,
    stage: 'active' | 'candidate' = 'active'
  ): Promise<any> {
    // 通过 ctx.tools 调用 genome_update
    const tool = this.ctx.tools.list().find(t => t.name === 'genome_update');
    if (!tool) {
      throw new Error('genome_update tool not found');
    }

    // @ts-ignore - tool.execute exists
    return await tool.execute({
      section,
      content,
      reason,
      stage,
      force: false,
    });
  }

  /**
   * 生成每日蒸馏摘要
   */
  private generateDistillSummary(
    distillResult: any,
    evolverResult: any,
    autoApply: boolean
  ): string {
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
      const results = evolverResult.results || [];
      const successCount = results.filter((r: any) => r.success).length;
      summary += `✅ 已应用: ${successCount}/${results.length} 条改进\n`;
    } else {
      summary += `⚠️  预览模式: 未实际应用改进（传 auto_apply=true 自动应用）\n`;
    }
    
    return summary;
  }
}
