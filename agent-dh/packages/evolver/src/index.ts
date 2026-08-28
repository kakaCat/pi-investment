/**
 * Evolver Plugin - Prompt Evolution Engine
 * P1-2: 接收 experience_distill 建议，生成段更新提案，调用 genome_update 应用
 * P2 (RFC 008): 验证门——提案应用为 candidate 观察版，观察期后裁决转正/回滚
 */
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
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
  // 2026-08-25 扩展：支持回测腿 + P4 元学习数据地基
  mutation_type?: 'prompt' | 'rule' | 'strategy_param';  // 变异类型（P4 归因用）
  strategy_id?: number;       // 策略参数类 candidate 关联的策略 ID
  params_override?: any;      // 参数变体（未来用）
  backtest_verdict?: {        // 回测腿裁决结果（P4 元学习用）
    passed: boolean;
    windows: Array<{
      label: string;
      symbol: string;
      start_date: string;
      end_date: string;
      sharpe: number;
      return_pct: number;
      max_drawdown_pct: number;
    }>;
    reason: string;
  };
}

export default class EvolverPlugin extends Service {
  static inject = ['tools', 'genome', 'llm'];  // 依赖 genome 插件 + LLM（段落改写）

  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
    }).default({} as any),
    observeDays: z.number().default(5),  // 模拟盘观察期（交易日）
    llmProvider: z.string().default('deepseek-official'),  // LLM 改写路由
    llmModel: z.string().default('deepseek-v4-flash'),
  }).default({} as any);

  private qv2: QuantsysV2Client;
  private osMemory: OsMemoryStore;
  private observeDays: number;
  private llmProvider: string;
  private llmModel: string;

  constructor(ctx: Context, config: any) {
    super(ctx, 'evolver');
    this.qv2 = new QuantsysV2Client({ baseURL: config?.quantsysV2?.baseURL || 'http://localhost:5001' });
    this.osMemory = new OsMemoryStore({ baseURL: (config as any).agentOS?.baseURL || 'http://localhost:8080', agentId: (config as any).agentOS?.agentId || 'agent-dh' });
    this.observeDays = config?.observeDays || 5;
    this.llmProvider = config?.llmProvider || 'deepseek-official';
    this.llmModel = config?.llmModel || 'deepseek-v4-flash';
    this.registerTools();
  }

  /**
   * LLM 段落改写（2026-08-20 任务#3：替代 naive 追加）
   * 让模型理解段落后整体重写，融入改进建议；失败时回退追加（保证可用性）。
   * 护栏：输出 ≤8000 字符（genome_update 还会再校验）、rules 段规则 ID 只允许增不允许静默删。
   */
  private async llmRewriteSection(section: string, currentContent: string, suggestion: any): Promise<{ content: string; method: 'llm' | 'append_fallback' }> {
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

      // 去掉可能的代码块包裹
      const cleaned = text.replace(/^```(?:markdown|md)?\s*\n?/i, '').replace(/\n?```\s*$/i, '').trim();
      if (cleaned.length < 50 || cleaned.length > 7800) {
        throw new Error(`LLM 输出长度异常（${cleaned.length} 字符），回退追加模式`);
      }
      return { content: cleaned + '\n', method: 'llm' };
    } catch (e: any) {
      this.ctx.logger('evolver').warn(`LLM rewrite failed, fallback to append: ${e?.message}`);
      return { content: currentContent.trim() + '\n' + (suggestion.content || ''), method: 'append_fallback' };
    }
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

  private registerCandidate(
    section: string,
    sectionVersion: number,
    genomeVersion: string,
    baselineVersion: string,
    observeDays?: number,
    mutationType: 'prompt' | 'rule' | 'strategy_param' = 'prompt',
    strategyId?: number,
    paramsOverride?: any
  ): CandidateRecord {
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
      mutation_type: mutationType,
      strategy_id: strategyId,
      params_override: paramsOverride,
    };
    const list = this.readCandidates();
    list.push(rec);
    this.writeCandidates(list);
    return rec;
  }

  /** 从记忆库取某基因组代数的打标经验奖励（P0-3 打标的消费端） */
  private async searchRewards(genomeVersion: string): Promise<{ count: number; avg: number }> {
    try {
      const res = await this.osMemory.searchMemory({ q: `genome:${genomeVersion}`, kind: 'experience', limit: 50 });
      const items = res?.items || [];
      const rewards: number[] = [];
      for (const it of items) {
        try {
          // 2026-08-20 验收修复：BM25 文本检索 genome:gN 会串版本（g7/g8 互相命中），
          // 必须按 payload.genome_context.genome_version 精确过滤，裁决才公平
          const tagged = it.payload?.genome_context?.genome_version;
          if (tagged !== genomeVersion) continue;
          const content = typeof it.content === 'string' ? JSON.parse(it.content) : it.content;
          if (typeof content?.reward === 'number') {
            // 2026-08-25 审计修复 #2：过滤占位奖励——只统计真实交易的 reward（portfolio_trade/algo_execute）
            // 排除 model_predict/opportunity_scan 等分析类工具的占位值（0.1/0.5），避免噪音污染基线
            const tool = content?.action?.tool;
            if (tool && !['portfolio_trade', 'algo_execute'].includes(tool)) continue;
            rewards.push(content.reward);
          }
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

      // 2026-08-25 新增：回测腿（第一级门）—— 策略类 candidate 先过回测
      // 修正：改用全区间单窗口（短窗口 MA60 策略信号稀疏），宽松门槛（只拦截明显垃圾）
      if (c.strategy_id && c.mutation_type !== 'prompt') {
        const backtestWindows = [
          { label: '全区间', symbol: '002716', start_date: '2025-01-02', end_date: '2026-08-21' },  // 湖南白银代表性活跃标的
        ];
        const results: any[] = [];
        let passed = true;
        let reason = '';

        try {
          for (const w of backtestWindows) {
            const res = await this.callTool('strategy_execute', {
              strategy_id: c.strategy_id,
              mode: 'backtest',
              symbols: [w.symbol],
              start_date: w.start_date,
              end_date: w.end_date,
              initial_capital: 100000,
            });
            // 2026-08-25 审计修复：strategy_execute 返回的是平铺的回测结果
            //（totalReturn/sharpeRatio 在顶层），不存在 backtest_result 嵌套——
            // 原解析读到空对象导致全零误判。兼容三种形状：嵌套 data / 嵌套 / 平铺。
            const bt = res?.backtest_result?.data ?? res?.backtest_result ?? res ?? {};
            results.push({
              label: w.label,
              symbol: w.symbol,
              start_date: w.start_date,
              end_date: w.end_date,
              sharpe: bt.sharpeRatio ?? 0,
              return_pct: (bt.totalReturn ?? 0) * 100,
              max_drawdown_pct: (bt.maxDrawdown ?? 0) * 100,
            });
            // 拒绝条件放宽：夏普 <0（亏钱策略）或 回撤 <-30%（超激进）或 0 信号（策略根本没执行）
            const isBad = (bt.sharpeRatio ?? 0) < 0 || (bt.maxDrawdown ?? 0) < -0.30 || (bt.totalTrades ?? 0) === 0;
            if (isBad) {
              passed = false;
              reason = `回测腿拒绝：${w.label} sharpe=${(bt.sharpeRatio ?? 0).toFixed(2)} mdd=${((bt.maxDrawdown ?? 0) * 100).toFixed(1)}% trades=${bt.totalTrades ?? 0}`;
            }
          }
        } catch (e: any) {
          passed = false;
          reason = `回测腿异常：${e.message}`;
        }

        c.backtest_verdict = { passed, windows: results, reason: reason || '回测达标' };

        if (!passed) {
          c.status = 'rejected';
          c.note = `回测腿拒绝：${reason}`;
          verdicts.push({ id: c.id, section: c.section, verdict: 'rejected_by_backtest', backtest_verdict: c.backtest_verdict });
          this.writeCandidates(list);
          continue;  // 跳过观察门，省 5 天
        }
      }

      // 第二级门：模拟盘观察门（原逻辑）
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

      // 2026-08-25 审计修复 #1：硬样本门槛——candidate 期零样本时无论 force 与否都不能转正
      // （g10 首次真实裁决暴露：cand.count=0 时 cand.avg=0，与 base 比较会误判"不劣于"转正）
      if (cand.count === 0) {
        c.observe_until = new Date(now + 2 * 86400000).toISOString();
        c.note = `零样本拒绝转正（candidate 期无数据，统计无效）`;
        verdicts.push({ id: c.id, section: c.section, verdict: 'extended', cand_samples: 0, note: c.note });
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
                  method: { type: 'string', description: 'llm=LLM 改写 / append=规则追加 / append_fallback=LLM 失败回退' },
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
        const { suggestions } = args;
        // 2026-08-20 验收修复：dsh-tools 不注入 schema 默认值，undefined ≠ true
        // （验收时未传 dry_run 导致默认预览失效、直接应用了 candidate）。
        // 安全默认值必须在 execute 内显式兜底：未传 = 预览（true），显式 false 才应用。
        const dry_run = args.dry_run !== false;
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
          let method: string = 'append';

          // 根据 type 生成新内容
          if (suggestion.type === 'add_rule') {
            // 新增规则保持追加（规则是增量式的；LLM 改写有静默丢规则 ID 的风险）
            newContent = currentContent.trim() + '\n' + suggestion.content;
            action = 'add';
          } else if (suggestion.type === 'modify_principle') {
            // 原则/教训类段落：LLM 理解后整体改写（2026-08-20 任务#3），失败回退追加
            const rewrite = await this.llmRewriteSection(section, currentContent, suggestion);
            newContent = rewrite.content;
            method = rewrite.method;
            action = 'modify';
          }

          // 生成 diff 预览
          const preview_diff = this.generateDiff(currentContent, newContent);

          const proposal = {
            section,
            action,
            method,  // llm（LLM 改写）/ append（规则追加）/ append_fallback（LLM 失败回退）
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
            rule_gate_result: {
              type: 'object',
              description: 'P3 规则级验证门结果（淘汰/强化提案）',
              additionalProperties: true,
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
        // 安全默认值显式兜底（dsh-tools 不注入 schema 默认值）：
        // days 默认 7；auto_apply 默认 false（未传=预览，显式 true 才应用为 candidate）
        const days = args.days ?? 7;
        const auto_apply = args.auto_apply === true;

        // Step 0（RFC 008）：先裁决到期的观察期候选（转正/回滚/延期）
        const adjudication = await this.judgeCandidates(false);

        // Step 0.5（P3，2026-08-28）：规则级验证门——读 rule_scoreboard 按规则表现生成淘汰/强化提案
        let ruleGateResult: any = null;
        try {
          ruleGateResult = await this.callTool('rule_gate', { dry_run: true, min_samples: 3 });
        } catch (e: any) {
          // rule_gate 失败不阻塞主流程（经验蒸馏仍可继续）
          console.warn('[daily_distill] rule_gate failed:', e.message);
        }

        // Step 1: experience_distill
        const distillResult = await this.callTool('experience_distill', { days });

        // Step 2: prompt_evolver
        const suggestions = distillResult.suggestions || [];
        const evolverResult = await this.callTool('prompt_evolver', {
          suggestions,
          dry_run: !auto_apply,
        });

        // Step 3: 生成摘要
        const summary = this.generateDistillSummary(distillResult, evolverResult, auto_apply);

        // Step 4: 写入 memory（记录蒸馏历史，非关键操作失败不影响主流程）
        try {
          await this.callTool('memory_write', {
            content: `每日蒸馏 ${new Date().toISOString()}: ${summary}`,
            namespace: 'decision',
            importance: 0.8,
            tags: ['daily_distill', 'genome_evolution'],
          });
        } catch (e) {
          // 非关键操作，失败不影响主流程
        }

        return {
          distill_result: distillResult,
          evolver_result: evolverResult,
          adjudication,
          rule_gate_result: ruleGateResult,
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
      description: '验证门裁决（两级门）：①回测腿（策略类 candidate）：三窗口回测（牛/熊/震荡），夏普<0.5 或回撤<-15% 当场拒绝（省 5 天观察期）；②模拟盘观察门（所有类型）：对比基准期打标经验，达标转正（genome_promote）、显著恶化回滚（genome_rollback）、证据不足延期。提示词类 candidate 跳过回测腿直接进观察门。force=true 跳过时间与样本门槛（验收/人工裁决用）。',
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

    // 5. 规则级验证门（RFC 009，方案 A 共享数据层，2026-08-26）
    this.ctx.tools.register(defineTool({
      name: 'rule_gate',
      description: '规则级验证门（RFC 009）：读 rule_scoreboard 共享成绩单（analytics:rule_scoreboard），按单条 R-xxx 规则表现生成裁决提案——淘汰（avg_reward<-0.1 且样本≥3）、强化（avg_reward>0.3 且成功率>0.7 且样本≥5）、固化（成功率>0.8 且样本≥10）。淘汰/强化走 candidate 观察可逆。dry_run 默认 true 只预览；false 时自动调 genome_update 落地提案。',
      parameters: {
        dry_run: { type: 'boolean', description: 'true（默认）：只预览提案不执行；false：自动调 genome_update 落地提案', default: true },
        min_samples_deprecate: { type: 'number', description: '淘汰提案最小样本数，默认 3', default: 3 },
        min_samples_strengthen: { type: 'number', description: '强化提案最小样本数，默认 5', default: 5 },
        min_samples_promote: { type: 'number', description: '固化提案最小样本数，默认 10', default: 10 },
      },
      output: {
        schema: { type: 'object', properties: { proposals: { type: 'array' }, executed: { type: 'boolean' }, note: { type: 'string' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        // 直接读经验库并计算规则成绩（复制 learning 插件 rule_scoreboard 逻辑，用 osMemory 避开跨插件调用）
        let experiences: any[] = [];
        try {
          const res = await this.osMemory.searchMemory({ kind: 'experience', limit: 200 });
          const items = res?.items || [];
          experiences = items.map((it: any) => {
            let content: any = {};
            try { content = typeof it.content === 'string' ? JSON.parse(it.content) : (it.content ?? {}); } catch { return null; }
            const reward = typeof content?.reward === 'number' ? content.reward : (typeof it.payload?.reward === 'number' ? it.payload.reward : 0);
            const gc = content?.genome_context ?? it.payload?.genome_context;
            return {
              action: content.action ?? {},
              outcome: content.outcome ?? { success: true },
              reward,
              genome_context: gc,
            };
          }).filter((e: any) => e && typeof e.reward === 'number');
        } catch (e: any) {
          // Agent OS (8080) 服务不稳定时降级返回友好消息（不阻塞工具上线）
          return { proposals: [], executed: false, note: `RFC 009 rule_gate 工具框架已上线。当前 Agent OS 服务暂不可用（${e.message}），数据读取待服务恢复 + R-005 真实成交积累 1-2 周后自动生效。` };
        }

        if (experiences.length === 0) {
          return { proposals: [], executed: false, note: '暂无经验数据（等 R-005 真实成交积累后自动生效）' };
        }

        // 按 R-ID 聚合成绩（learning 插件 rule_scoreboard 逻辑）
        const ruleMap = new Map<string, { count: number; rewards: number[]; successes: number }>();
        for (const e of experiences) {
          const ids = new Set<string>(e.genome_context?.rules_used ?? []);
          // 从全文扫 R-ID（兼容旧数据）
          try {
            const text = JSON.stringify([e.action, e.outcome]).slice(0, 30000);
            for (const m of text.matchAll(/\b(R-\d{3})\b/g)) ids.add(m[1]);
          } catch {}

          for (const id of ids) {
            if (!ruleMap.has(id)) ruleMap.set(id, { count: 0, rewards: [], successes: 0 });
            const r = ruleMap.get(id)!;
            r.count++;
            r.rewards.push(e.reward);
            if (e.outcome?.success) r.successes++;
          }
        }

        const rules = [...ruleMap.entries()].map(([rule_id, r]) => ({
          rule_id,
          count: r.count,
          avg_reward: +(r.rewards.reduce((a, b) => a + b, 0) / r.rewards.length).toFixed(3),
          success_rate: +(r.successes / r.count).toFixed(3),
        }));

        if (rules.length === 0) {
          return { proposals: [], executed: false, note: `扫描 ${experiences.length} 条经验，未提取到 R-ID（等 R-005 真实成交积累后自动生效）` };
        }

        const proposals: any[] = [];
        const thresholds = {
          deprecate: { min_samples: args.min_samples_deprecate || 3, max_avg_reward: -0.1 },
          strengthen: { min_samples: args.min_samples_strengthen || 5, min_avg_reward: 0.3, min_success_rate: 0.7 },
          promote: { min_samples: args.min_samples_promote || 10, min_success_rate: 0.8 },
        };

        for (const r of rules) {
          if (r.count >= thresholds.deprecate.min_samples && r.avg_reward < thresholds.deprecate.max_avg_reward) {
            proposals.push({ type: 'deprecate', rule_id: r.rule_id, reason: `样本 ${r.count} 条、平均奖励 ${r.avg_reward}（< -0.1）`, action: `从 rules 段移除（走 candidate 观察可逆）` });
          } else if (r.count >= thresholds.strengthen.min_samples && r.avg_reward > thresholds.strengthen.min_avg_reward && r.success_rate > thresholds.strengthen.min_success_rate) {
            proposals.push({ type: 'strengthen', rule_id: r.rule_id, reason: `样本 ${r.count} 条、平均奖励 ${r.avg_reward}、成功率 ${(r.success_rate * 100).toFixed(1)}%`, action: `规则精髓提炼进 principles（走 candidate 观察）` });
          } else if (r.count >= thresholds.promote.min_samples && r.success_rate > thresholds.promote.min_success_rate) {
            proposals.push({ type: 'promote', rule_id: r.rule_id, reason: `样本 ${r.count} 条、成功率 ${(r.success_rate * 100).toFixed(1)}%（> 80%）`, action: `标记"已验证"（history 留痕）` });
          }
        }

        if (proposals.length === 0) {
          return { proposals: [], executed: false, note: `扫描 ${rules.length} 条规则，无提案（门槛：deprecate avg<-0.1 n≥3, strengthen avg>0.3 rate>0.7 n≥5, promote rate>0.8 n≥10）` };
        }

        if (args.dry_run !== false) {
          return { proposals, executed: false, note: `预览模式：${proposals.length} 条提案待评审（传 dry_run=false 自动执行）` };
        }

        // 执行提案（dry_run=false）
        const executed: any[] = [];
        for (const p of proposals) {
          try {
            if (p.type === 'deprecate') {
              const rulesContent = await this.readSection('rules');
              const lines = rulesContent.split('\n');
              const filtered = lines.filter(line => !line.match(new RegExp(`^##\\s+${p.rule_id}\\b`)));
              const newContent = filtered.join('\n');
              await this.callGenomeUpdate('rules', newContent, `rule_gate 淘汰提案：${p.rule_id}（${p.reason}）`, 'candidate');
              executed.push({ ...p, result: 'candidate 已生成，待观察期裁决' });
            } else if (p.type === 'strengthen') {
              const principlesContent = await this.readSection('principles');
              const essence = `**${p.rule_id} 验证有效**（${p.reason}）：该规则的成功经验已验证，持续遵守。`;
              const newContent = `${principlesContent.trim()}\n\n${essence}\n`;
              await this.callGenomeUpdate('principles', newContent, `rule_gate 强化提案：${p.rule_id}（${p.reason}）`, 'candidate');
              executed.push({ ...p, result: 'principles candidate 已生成' });
            } else if (p.type === 'promote') {
              executed.push({ ...p, result: 'promote 路径待实现（标记"已验证"入 history）' });
            }
          } catch (e: any) {
            executed.push({ ...p, result: `执行失败: ${e.message}` });
          }
        }

        return { proposals, executed: true, results: executed, note: `已执行 ${executed.length}/${proposals.length} 条提案` } as any;
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
    return await this.callTool('genome_update', {
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
