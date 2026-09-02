/**
 * Evolver Plugin - Prompt Evolution Engine
 * P1-2: 接收 experience_distill 建议，生成段更新提案，调用 genome_update 应用
 * P2 (RFC 008): 验证门——提案应用为 candidate 观察版，观察期后裁决转正/回滚
 */
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import {
  createPromptEvolverTool,
  createValidationGateTool,
  createDailyDistillTool,
  createWeeklyReportTool,
} from './tools';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Minimal OsMemoryStore replacement (inlined from deleted @pi-investment/os-memory)
 * Wraps AgentOSClient to provide createMemory/searchMemory API
 */
export class OsMemoryStore {
  private client: AgentOSClient;
  private agentId: string;
  private baseURL: string;

  constructor(opts: { baseURL?: string; agentId?: string } = {}) {
    this.baseURL = opts.baseURL || 'http://localhost:8080';
    this.client = new AgentOSClient({
      baseURL: this.baseURL,
      agentId: opts.agentId || 'agent-dh',
    });
    this.agentId = opts.agentId || 'agent-dh';
  }

  async createMemory(entry: { kind: string; scope: string; title: string; content: string; payload?: any; status?: string; confidence?: number; source?: string; provenance?: any }): Promise<{ id: string }> {
    const category = entry.kind === 'experience' ? 'experience' : entry.kind === 'rule' ? 'knowledge' : entry.kind === 'decision' ? 'decision' : 'data';
    const envelope = { kind: entry.kind, scope: entry.scope, status: entry.status ?? 'testing', confidence: entry.confidence ?? 0.5, source: entry.source ?? 'agent', provenance: entry.provenance ?? null, payload: entry.payload ?? null, body: entry.content };
    const res: any = await (this.client.memory as any).write({ title: entry.title, content: JSON.stringify(envelope), category, tags: [entry.scope, `kind:${entry.kind}`, `agent:${this.agentId}`].filter(Boolean) });
    return { id: String(res?.id ?? res?.memory?.id ?? '') };
  }

  async searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<{ items: any[]; total: number; degraded: boolean; strategy: string }> {
    const q = params.q ?? '';
    const limit = params.limit ?? 20;
    const url = `${this.baseURL}/api/v1/memory/search?q=${encodeURIComponent(q || ' ')}&limit=${Math.min(limit * 3, 150)}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`OS memory search failed: HTTP ${resp.status}`);
    const res: any = await resp.json();
    const raw: any[] = res?.memories ?? res?.items ?? [];
    const items: any[] = [];
    for (const it of raw) {
      let env: any = null;
      try { env = typeof it.content === 'string' ? JSON.parse(it.content) : it.content; } catch { continue; }
      if (!env || typeof env !== 'object' || env.kind === undefined) continue;
      if (params.kind && env.kind !== params.kind) continue;
      if (params.scope && env.scope !== params.scope) continue;
      if (env.status === 'deprecated') continue;
      items.push({ id: it.id, kind: env.kind, scope: env.scope, title: it.title, content: env.body ?? '', payload: env.payload, status: env.status, confidence: env.confidence, source: env.source, provenance: env.provenance, created_at: it.created_at });
      if (items.length >= limit) break;
    }
    return { items, total: items.length, degraded: false, strategy: 'os-text' };
  }
}

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
  private qv2BaseURL: string;

  constructor(ctx: Context, config: any) {
    super(ctx, 'evolver');
    this.qv2BaseURL = config?.quantsysV2?.baseURL || 'http://localhost:5001';
    this.qv2 = new QuantsysV2Client({ baseURL: this.qv2BaseURL });
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
    const { ctx, osMemory, llmProvider, llmModel, observeDays } = this;

    // 1. Prompt Evolver - 接收 experience_distill 建议，生成段更新提案，调用 genome_update 应用
    ctx.tools.register(createPromptEvolverTool(ctx, osMemory, llmProvider, llmModel, observeDays));

    // 2. Validation Gate - RFC 008: 验证门——提案应用为 candidate 观察版，观察期后裁决转正/回滚
    ctx.tools.register(createValidationGateTool(ctx, osMemory, observeDays));

    // 3. Daily Distill - 每日蒸馏编排：experience_distill → prompt_evolver
    ctx.tools.register(createDailyDistillTool(ctx, osMemory));

    // 4. Weekly Report - M6 学习飞轮周报：封装后端 /api/reports/weekly
    //    （2026-09-03 补：原 prompt 引用 weekly_report 但 agent 侧无此工具 → 业务空转）
    ctx.tools.register(createWeeklyReportTool(this.qv2BaseURL));
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
