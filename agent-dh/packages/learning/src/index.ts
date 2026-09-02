/**
 * Learning Plugin - Experience Learning & Distillation
 * 经验学习、蒸馏和知识萃取
 */
import { Context, Service } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { readFileSync } from 'node:fs';

// 导入 BaseTool 工具
import {
  LearningTrackTool,
  LearningAnalyzeTool,
  LearningDistillTool,
  LearningApplyTool,
  ReflectTool,
} from './tools';

/**
 * Minimal OsMemoryStore replacement (inlined from deleted @pi-investment/os-memory)
 * Wraps AgentOSClient to provide createMemory/searchMemory API
 */
class OsMemoryStore {
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

  /**
   * 2026-09-03 Fix③：patch 一条记忆。
   * status 是 envelope 的一部分（存于 content JSON 内），转正须整体重写 content：
   * 传 rebuild 函数，输入当前解析后的 envelope（含顶层 metadata），输出新的 envelope 对象，
   * 由本方法负责 JSON.stringify 后 PATCH 回去。返回 PATCH 响应。
   */
  async patchMemory(id: string, opts: {
    rebuild?: (env: any, meta: Record<string, any>) => { envelope: any; metadataPatch?: Record<string, any> };
  }): Promise<any> {
    // 先 GET 当前记忆（envelope 在 content 字段）
    const mem: any = await (this.client.memory as any).getById(id);
    const current = mem?.content ?? mem?.memory?.content ?? null;
    const env = typeof current === 'string' ? JSON.parse(current) : current;
    if (!env || typeof env !== 'object' || env.kind === undefined) {
      throw new Error(`memory ${id} 不是 envelope 格式（kind 缺失），无法 patch`);
    }
    const metadata = (mem?.metadata ?? mem?.memory?.metadata) || {};
    const { envelope, metadataPatch } = opts.rebuild
      ? opts.rebuild(env, metadata)
      : { envelope: env, metadataPatch: undefined };
    const res: any = await (this.client.memory as any).patchMemory(id, {
      content: JSON.stringify(envelope),
      metadataPatch,
    });
    return res;
  }
}

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
  learning?: {
    minSamplesForPattern?: number;
    rewardDecayFactor?: number;
    distillConfidenceThreshold?: number;
  };
}

/**
 * Learning Plugin for Agent-DH
 *
 * 自我学习核心：经验追踪、模式挖掘、知识蒸馏、策略优化
 * 
 * 实现 RFC 003: Self-Learning and Distillation System
 */
export default class LearningPlugin extends Service {
  static inject = ['tools', 'memory', 'genome'];  // P0-3: 添加 genome 依赖
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
    learning: z.object({
      minSamplesForPattern: z.number().default(10),
      rewardDecayFactor: z.number().default(0.95),
      distillConfidenceThreshold: z.number().default(0.7),
    }).default({} as any),
    agentsFile: z.string().default('~/.dsh/profiles/investment/agents.json'),  // 身份注册表
  }).default({} as any)

  private qv2: QuantsysV2Client;
  private osMemory: OsMemoryStore;
  private experienceBuffer: ExperienceEntry[] = [];
  private agentIdentity: { id: string; name: string; instance: string };

  constructor(ctx: Context, config: Config) {
    super(ctx, 'learning');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.osMemory = new OsMemoryStore({ baseURL: (config as any).agentOS?.baseURL || 'http://localhost:8080', agentId: (config as any).agentOS?.agentId || 'agent-dh' });
    this.agentIdentity = this.loadAgentIdentity((config as any).agentsFile);
    this.registerTools();
    this.setupInterceptors();
  }

  /**
   * 读身份注册表（agents.json），取 primary 主身份——
   * 本进程所有工具调用都服务于投资主身份（2026-08-21 身份系统）
   */
  private loadAgentIdentity(file?: string): { id: string; name: string; instance: string } {
    const fallback = { id: 'investor', name: 'PI 投资顾问·投资脑', instance: 'investment' };
    try {
      const p = (file || '').replace(/^~/, process.env.HOME || '');
      const registry = JSON.parse(readFileSync(p, 'utf-8'));
      const primary = (registry.agents || []).find((a: any) => a.primary) || (registry.agents || [])[0];
      if (!primary) return fallback;
      return {
        id: primary.id,
        name: primary.name,
        instance: registry.instance?.name ?? registry.instance?.id ?? 'unknown',
      };
    } catch {
      return fallback;
    }
  }

  /**
   * 设置拦截器：自动追踪工具调用
   */
  private setupInterceptors(): void {
    // 自动追踪工具调用。
    // ⚠️ 2026-08-20 验收修复：原实现监听 'tool/before-execute'/'tool/after-execute'，
    // 这两个事件在整个 DSH 中不存在，自动追踪从不触发（与 genome ready 事件同类 bug）。
    // dsh-tools 的真实扩展点是 waterfall：tools/pre-execute / tools/execute / tools/post-execute。
    //
    // waterfall 监听器两条铁律（违反会破坏工具调用本身）：
    // ① 必须把 prev 原样返回（返回 undefined 会让后续链路拿到 undefined 而崩溃）
    // ② 绝不能抛异常（监听器抛错会把工具结果变成 isError）
    const startTimes = new Map<string, number>();

    this.ctx.on('tools/pre-execute' as any, (exec: any, prev: any) => {
      try {
        if (exec?.callId) startTimes.set(exec.callId, Date.now());
      } catch { /* 观察者不能影响工具调用 */ }
      return prev;
    });

    this.ctx.on('tools/post-execute' as any, (exec: any, result: any, prev: any) => {
      try {
        const toolName: string | undefined = exec?.name;
        if (toolName && this.isTrackedTool(toolName)) {
          const startedAt = exec?.callId ? startTimes.get(exec.callId) : undefined;
          if (exec?.callId) startTimes.delete(exec.callId);
          const isError = result?.isError === true;
          this.autoTrack({
            tool: toolName,
            args: exec?.arguments,
            result: result?.isError ? undefined : result,
            duration: startedAt ? Date.now() - startedAt : 0,
            success: !isError,
            error: isError ? (result?.error?.message ?? 'tool error') : undefined,
            window_id: exec?.agent?.id,  // 窗口唯一编码（2026-08-21 双层身份：角色+窗口）
          }).catch(() => {});
        }
      } catch { /* 观察者不能影响工具调用 */ }
      return prev;
    });
  }

  /**
   * 判断是否需要追踪该工具
   */
  private isTrackedTool(toolName: string): boolean {
    const tracked = [
      'portfolio_trade',
      'strategy_execute',
      'model_predict',
      'opportunity_scan',
      'rotation_execute',
    ];
    return tracked.includes(toolName);
  }

  /**
   * 自动追踪工具调用
   */
  private async autoTrack(execution: any): Promise<void> {
    const entry: ExperienceEntry = {
      id: `exp_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      timestamp: new Date().toISOString(),
      agent_version: process.env.AGENT_VERSION || 'dev',
      action: {
        tool: execution.tool,
        args: this.truncateForMemory(execution.args),
      },
      context: await this.captureContext(execution),
      outcome: {
        success: execution.success,
        result: this.truncateForMemory(execution.result),
        error: execution.error,
        duration_ms: execution.duration,
      },
      reward: await this.calculateReward(execution),
      tags: this.extractTags(execution),
      genome_context: this.captureGenomeContext(execution),  // P0-3: 决策打标
    };

    // 存入内存缓冲区
    this.experienceBuffer.push(entry);
    
    // 异步持久化到 memory
    this.persistExperience(entry).catch(err => {
      this.ctx.logger.warn(`learning: failed to persist experience: ${err}`);
    });
  }

  /**
   * 捕获当前上下文（市场状态、持仓等）
   */
  private async captureContext(execution?: any): Promise<any> {
    try {
      // 简化版：实际应该调用多个工具获取完整上下文
      return {
        timestamp: new Date().toISOString(),
        agent: {
          ...this.agentIdentity,  // 角色身份（每窗口相同）
          window: execution?.window_id ?? null,  // 窗口唯一编码（每窗口不同）
        },
        // 可扩展：market_phase, portfolio_state, etc.
      };
    } catch {
      return {};
    }
  }

  /**
   * P0-3: 捕获基因组上下文（genome_version + rules_used）
   */
  private captureGenomeContext(execution?: any): { genome_version: string; rules_used: string[] } | undefined {
    try {
      // @ts-ignore - genome 插件通过 inject 动态注入
      const genome = this.ctx.genome;
      if (!genome || !genome.genomeData) {
        return undefined;
      }

      return {
        genome_version: genome.genomeData.genome_version,
        rules_used: this.extractRulesFromContext(execution),
      };
    } catch (error) {
      this.ctx.logger('learning').warn('Failed to capture genome context:', error);
      return undefined;
    }
  }

  /**
   * 截断过大的值：防止几十 KB 的工具结果整体塞入记忆库（2026-08-20 遗留①）
   * 超过 maxChars 时替换为带预览的占位对象
   */
  private truncateForMemory(value: any, maxChars = 2000): any {
    if (value === undefined || value === null) return value;
    try {
      const text = typeof value === 'string' ? value : JSON.stringify(value);
      if (text.length <= maxChars) return value;
      return {
        _truncated: true,
        _original_chars: text.length,
        preview: text.slice(0, maxChars) + '…[truncated]',
      };
    } catch {
      return undefined;
    }
  }

  /**
   * P0-3: 从决策上下文提取规则 ID（2026-08-20 遗留②实现）
   * 来源：工具参数 + 结果文本中引用的 R-\d{3}（如 portfolio_trade 的 reason 参数、
   * 决策说明中的"根据 R-001"）。配合 trading 插件的 reason 参数形成闭环：
   * 下单时注明依据的规则 ID → 归因时可按规则分组结算。
   */
  private extractRulesFromContext(execution?: any): string[] {
    if (!execution) return [];
    try {
      const text = JSON.stringify([execution.args ?? null, typeof execution.result === 'string'
        ? execution.result.slice(0, 20000)
        : null]);
      return [...new Set([...text.matchAll(/\b(R-\d{3})\b/g)].map(m => m[1]))].sort();
    } catch {
      return [];
    }
  }

  /**
   * 计算奖励信号（2026-08-20 起异步：交易类需查后端成本）
   */
  private async calculateReward(execution: any): Promise<number> {
    if (!execution.success) return -0.3;

    // 根据工具类型计算不同的奖励
    switch (execution.tool) {
      case 'portfolio_trade':
        // reward 真实化：卖出按买入成本计算真实 P&L；买入保持中性（真实奖惩在卖出时结算）
        return await this.tradeReward(execution);
      case 'strategy_execute':
        return execution.result?.signals?.length > 0 ? 0.3 : 0.1;
      default:
        return 0.1;
    }
  }

  /** 最近一次交易的 P&L%（供 extractTags 附带记录） */
  private lastTradePnlPct: number | undefined;

  /**
   * 交易奖励真实化（验证门裁决可信度的地基）
   * 2026-08-21 修正（review 专项发现）：后端真实响应是 items 不是 orders，
   * 且卖出记录自带 pnl/pnlPercent（后端含费用精确计算）——优先直接使用，
   * 无 pnlPercent 时回退到买入加权成本估算；再不行回退中性 0.1。
   * reward = clamp(pnlPercent / 10, -1, 1)（±10% 映射到 ±1）
   */
  private async tradeReward(execution: any): Promise<number> {
    try {
      const trade = execution.result?.value ?? execution.result;
      const action = String(trade?.action ?? execution.args?.action ?? '').toUpperCase();
      const symbol = trade?.symbol ?? execution.args?.symbol;
      const price = Number(trade?.price);

      this.lastTradePnlPct = undefined;
      if (action === 'BUY') return 0.1;
      if (action !== 'SELL' || !symbol || !(price > 0)) return 0.1;

      // 路径 1（首选）：后端卖出记录自带 pnlPercent（含费用精确计算）
      const sellHistory = await this.qv2.getTradeHistory({ symbol, direction: 'sell' });
      const sellOrders: any[] = sellHistory?.orders ?? sellHistory?.items ?? [];
      const matched = sellOrders
        .filter((o: any) => typeof o?.pnlPercent === 'number')
        .sort((a: any, b: any) => String(b?.createdAt ?? '').localeCompare(String(a?.createdAt ?? '')))[0];
      if (matched) {
        const pnlPct = Number(matched.pnlPercent);
        this.lastTradePnlPct = pnlPct;
        return Math.max(-1, Math.min(1, +(pnlPct / 10).toFixed(3)));
      }

      // 路径 2（回退）：买入加权平均成本估算
      const buyHistory = await this.qv2.getTradeHistory({ symbol, direction: 'buy' });
      const buyOrders: any[] = (buyHistory?.orders ?? buyHistory?.items ?? []).filter(
        (o: any) => Number(o?.price) > 0 && Number(o?.quantity) > 0
      );
      if (buyOrders.length === 0) return 0.1;

      const recent = buyOrders.slice(-10);
      const totalQty = recent.reduce((s, o) => s + Number(o.quantity), 0);
      const avgCost = recent.reduce((s, o) => s + Number(o.price) * Number(o.quantity), 0) / totalQty;

      const pnlPct = ((price - avgCost) / avgCost) * 100;
      this.lastTradePnlPct = +pnlPct.toFixed(2);
      return Math.max(-1, Math.min(1, +(pnlPct / 10).toFixed(3)));
    } catch {
      return 0.1;
    }
  }

  /**
   * 提取标签
   */
  private extractTags(execution: any): string[] {
    const tags: string[] = [execution.tool];
    if (execution.args?.symbol) tags.push(execution.args.symbol);
    if (execution.args?.strategy_id) tags.push(`strategy_${execution.args.strategy_id}`);
    // reward 真实化：卖出成交附带真实 P&L% 标签（归因可读性）
    if (execution.tool === 'portfolio_trade' && this.lastTradePnlPct !== undefined) {
      tags.push(`pnl_pct:${this.lastTradePnlPct}`);
    }
    return tags;
  }

  /**
   * 持久化经验到 memory
   */
  private async persistExperience(entry: ExperienceEntry): Promise<void> {
    // 2026-08-20 验收修复：genome_context（P0-3 打标）必须进入持久化内容，
    // 否则归因时检索不到打标数据；genome 代数同时进 tags 便于检索
    const content = JSON.stringify({
      action: entry.action,
      outcome: entry.outcome,
      reward: entry.reward,
      context: entry.context,
      genome_context: entry.genome_context,
    });

    const tags = entry.genome_context?.genome_version
      ? [...entry.tags, `genome:${entry.genome_context.genome_version}`]
      : entry.tags;

    // 2026-08-20 验收修复：client 没有 writeMemory 方法（原调用必抛 TypeError 且被静默吞掉）
    // 2026-08-25 记忆迁移：quantsys-v2 记忆写入停用，统一走 osMemory（Agent OS）
    await this.osMemory.createMemory({
      kind: 'experience',
      scope: 'global',
      title: `auto-track ${entry.action.tool} ${entry.outcome.success ? 'ok' : 'fail'} (${entry.genome_context?.genome_version ?? 'no-genome'})`,
      content,
      payload: {
        namespace: 'experience',
        tags,
        genome_context: entry.genome_context,
        entry_id: entry.id,
        ts: entry.timestamp,
      },
      status: 'testing',
      confidence: Math.min(1, Math.max(0.3, Math.abs(entry.reward))),
      source: 'learning_auto_track',
      provenance: { channel: 'dsh', session_kind: 'agent' },
    });
  }

  private registerTools(): void {
    const { ctx } = this;

    // 1. 追踪经验（重构为 BaseTool）
    const trackTool = new LearningTrackTool(
      this.experienceBuffer,
      this.persistExperience.bind(this),
      this.extractTagsFromContext.bind(this)
    );
    ctx.tools.register(defineTool(trackTool.toDSHToolDefinition()));

    // 2. 分析经验（重构为 BaseTool）
    const analyzeTool = new LearningAnalyzeTool(
      this.analyzeExperiences.bind(this)
    );
    ctx.tools.register(defineTool(analyzeTool.toDSHToolDefinition()));

    // 3. 提炼规则（重构为 BaseTool）
    // 2026-09-03 Fix③：传入 persistRules 回调——蒸馏产出即落库为 testing 候选，
    // 使 learning_apply 有真实可转正对象（distill→apply 闭环）
    const distillTool = new LearningDistillTool(
      this.loadExperiencesBySource.bind(this),
      this.distillRules.bind(this),
      this.getDistillMethod.bind(this),
      this.validateRules.bind(this),
      this.persistDistilledRules.bind(this)
    );
    ctx.tools.register(defineTool(distillTool.toDSHToolDefinition()));

    // 4. 应用规则（重构为 BaseTool）
    const applyTool = new LearningApplyTool(
      this.applyRule.bind(this)
    );
    ctx.tools.register(defineTool(applyTool.toDSHToolDefinition()));

    // 5. 目标对齐反思（2026-09-02，对标 agent-ts reflect；零依赖纯计算）
    const reflectTool = new ReflectTool();
    ctx.tools.register(defineTool(reflectTool.toDSHToolDefinition()));
  }

  // ===== 辅助方法 =====

  private extractTagsFromContext(context: any): string[] {
    const tags: string[] = [];
    if (context.symbol) tags.push(context.symbol);
    if (context.strategy_id) tags.push(`strategy_${context.strategy_id}`);
    if (context.action_type) tags.push(context.action_type);
    return tags;
  }

  /**
   * 分析经验库
   */
  private async analyzeExperiences(scope: string, focus: string, minSamples: number): Promise<any> {
    // 加载经验
    const experiences = await this.loadExperiences({ scope, minSamples });

    if (experiences.length < minSamples) {
      return {
        patterns: [],
        suggestions: [`样本数不足 (${experiences.length} < ${minSamples})，无法进行有效分析`],
        sample_count: experiences.length,
      };
    }

    // 挖掘模式
    const patterns = this.minePatterns(experiences, focus);

    // 生成改进建议
    const suggestions = this.generateImprovements(patterns);

    return {
      patterns,
      suggestions,
      sample_count: experiences.length,
    };
  }

  /**
   * 应用规则（2026-09-03 Fix③ 重写：去掉"假 applied:true"占位）
   *
   * 真实语义 = 规则生命周期状态机（与 Fix① genome candidate testing→active 同构）：
   *  - 规则先由 learning_distill 蒸馏落库为 kind='rule' status='testing' 候选（见 persistDistilledRules）
   *  - learning_apply 非 dryRun 把该记忆的 envelope status testing→active 重写，payload 记录
   *    applied_at/applied_by/applied_context，顶层 metadata 同步补审计键 → patch 成功且回读校验
   *    status==='active' 才返回 applied:true；patch 失败抛错（工具层失败，不伪装成功）
   *  - 规则不存在 → 诚实返回 applied:false + 指引（先 distill 落库）
   */
  private async applyRule(ruleId: string, context: any, dryRun: boolean): Promise<any> {
    // 从 OS 记忆库加载规则
    const searchResult = await this.osMemory.searchMemory({
      kind: 'rule',
      scope: 'global',
      q: ruleId,
      limit: 10,
    });

    // 精确匹配 rule_id
    const ruleRecords = searchResult.items.filter((item: any) => {
      const payload = item.payload || {};
      return payload.rule_id === ruleId || item.title?.includes(ruleId);
    });

    if (ruleRecords.length === 0) {
      return {
        applied: false,
        impact: { rule_id: ruleId },
        message: `规则 ${ruleId} 不存在（OS 记忆无 kind='rule' 记录）。请先 learning_distill 蒸馏落库（产出 rules 带 rule_id/memory_id），或检查 rule_id 拼写`,
      };
    }

    const record = ruleRecords[0];
    const rule = record.payload || {};
    const fromStatus = record.status || 'testing';
    const appliedAt = new Date().toISOString();
    const appliedBy = this.agentIdentity.id;

    // 模拟运行模式：返回将执行的状态迁移预览，不实际写入
    if (dryRun) {
      return {
        applied: false,
        action_taken: rule.action || '规则转正为 active',
        impact: {
          simulated: true,
          rule_id: ruleId,
          memory_id: record.id,
          current_status: fromStatus,
          target_status: 'active',
          will_record: { applied_at: appliedAt, applied_by: appliedBy, applied_context: context ?? {} },
          rule: rule.condition || null,
        },
        message: `模拟运行：规则 ${ruleId} 将执行 ${fromStatus} → active 状态迁移并记录应用审计（applied_at/applied_by/applied_context）；未实际写入`,
      };
    }

    if (fromStatus === 'active') {
      return {
        applied: true,
        action_taken: rule.action || '规则已处于 active',
        impact: { rule_id: ruleId, memory_id: record.id, from_status: 'active', to_status: 'active', already_active: true },
        message: `规则 ${ruleId} 已是 active（幂等：无需重复应用；若需更新应用上下文请先按需处理）`,
      };
    }

    // 真实应用 = 状态迁移 testing → active：重写 envelope + 顶层 metadata 审计
    await this.osMemory.patchMemory(record.id, {
      rebuild: (env: any, meta: Record<string, any>) => ({
        envelope: {
          ...env,
          status: 'active',
          payload: {
            ...(env.payload || {}),
            applied: true,
            applied_at: appliedAt,
            applied_by: appliedBy,
            applied_context: context ?? {},
          },
        },
        metadataPatch: {
          applied: true,
          applied_at: appliedAt,
          applied_by: appliedBy,
          status: 'active',
        },
      }),
    });

    // 回读校验：patch 后必须确认 status 已变 active（防"patch 未生效却报成功"）
    const verify = await this.osMemory.searchMemory({
      kind: 'rule',
      scope: 'global',
      q: ruleId,
      limit: 10,
    });
    const after = verify.items.find((it: any) => it.id === record.id);
    const promoted = !!after && after.status === 'active';
    if (!promoted) {
      throw new Error(`规则 ${ruleId} 状态迁移失败：patch 后回读 status=${after?.status ?? 'gone'}，期望 active（未报成功）`);
    }

    return {
      applied: true,
      action_taken: rule.action || '规则转正为 active',
      impact: {
        rule_id: ruleId,
        memory_id: record.id,
        from_status: fromStatus,
        to_status: 'active',
        applied_at: appliedAt,
        applied_by: appliedBy,
        applied_context: context ?? {},
      },
      message: `规则 ${ruleId} 已真实应用：${fromStatus} → active（记忆 ${record.id}，含应用审计）`,
    };
  }

  /**
   * 2026-09-03 Fix③：learning_distill 蒸馏产出规则后立即落库为 kind='rule' status='testing' 候选。
   * 这是 learning_apply 能检索到规则对象的前提（此前规则永不落库，apply 永远"规则不存在"）。
   * rule_id 用内容稳定哈希（condition+action+format），同规则重复蒸馏幂等复用同一记忆。
   * 落库失败的规则保留（纯计算产物仍可读），但显式带 persist_error 不伪装成功。
   */
  private async persistDistilledRules(rules: any[], meta: { source: string; target_format: string }): Promise<any[]> {
    const out: any[] = [];
    for (const rule of rules) {
      try {
        const condition = rule.condition ?? '';
        const action = rule.action ?? '';
        const format = meta.target_format ?? 'rule';
        const stableId = `rule_${this.fnv1a(`${condition}|${action}|${format}`)}`;
        // 幂等复用：同稳定 id 已落库则直接复用
        const existing = await this.findRuleByStableId(stableId);
        if (existing) {
          out.push({ ...rule, rule_id: stableId, memory_id: existing.id, status: existing.status || 'testing', reused: true });
          continue;
        }
        const { id } = await this.osMemory.createMemory({
          kind: 'rule',
          scope: 'global',
          title: `distilled rule ${stableId}`,
          content: `${condition}\n→ ${action}`,
          payload: {
            rule_id: stableId,
            condition,
            action,
            confidence: rule.confidence,
            format,
            source: meta.source,
            source_experiences: rule.source_experiences,
            distilled_at: new Date().toISOString(),
          },
          status: 'testing',
          confidence: typeof rule.confidence === 'number' ? rule.confidence : 0.6,
          source: 'learning_distill',
          provenance: { tool: 'learning_distill', channel: 'dsh', format },
        });
        out.push({ ...rule, rule_id: stableId, memory_id: id, status: 'testing' });
      } catch (e: any) {
        out.push({ ...rule, persist_error: String(e?.message || e), persisted: false });
      }
    }
    return out;
  }

  private async findRuleByStableId(stableId: string): Promise<any | null> {
    const res = await this.osMemory.searchMemory({ kind: 'rule', scope: 'global', q: stableId, limit: 10 });
    return (res.items || []).find((it: any) => (it.payload || {}).rule_id === stableId) || null;
  }

  private fnv1a(str: string): string {
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return (h >>> 0).toString(36);
  }

  /**
   * 从 memory 库加载持久化经验（2026-08-22 修复：重启后缓冲区为空，
   * 盘后例程的蒸馏/分析永远"无数据"；必须读库而非只读进程内 buffer）
   */
  private async loadPersistedExperiences(options: { sinceTs?: number; genomeVersion?: string }): Promise<ExperienceEntry[]> {
    try {
      const res = await this.osMemory.searchMemory({ kind: 'experience', limit: 100 });
      const items = res?.items || [];
      const since = options.sinceTs ?? 0;
      return items
        .map((it: any): ExperienceEntry | null => {
          let content: any = {};
          try { content = typeof it.content === 'string' ? JSON.parse(it.content) : (it.content ?? {}); } catch { return null; }
          const gc = content?.genome_context ?? it.payload?.genome_context;
          return {
            id: it.payload?.entry_id ?? String(it.id ?? ''),
            timestamp: it.payload?.ts ?? it.created_at ?? new Date().toISOString(),
            agent_version: 'persisted',
            action: content.action ?? { tool: 'unknown' },
            context: content.context ?? {},
            outcome: content.outcome ?? { success: true },
            reward: typeof content?.reward === 'number' ? content.reward : 0,
            tags: it.payload?.tags ?? [],
            genome_context: gc,
          } as ExperienceEntry;
        })
        .filter((e): e is ExperienceEntry => e !== null)
        .filter(e => new Date(e.timestamp).getTime() >= since)
        .filter(e => !options.genomeVersion || e.genome_context?.genome_version === options.genomeVersion);
    } catch {
      return [];
    }
  }

  private async loadExperiences(options: any): Promise<ExperienceEntry[]> {
    // 优先读库；库不可用/为空时回退进程内缓冲区
    const sinceTs = options?.timeRangeDays
      ? Date.now() - options.timeRangeDays * 86400000
      : 0;
    const persisted = await this.loadPersistedExperiences({ sinceTs });
    return persisted.length > 0 ? persisted : this.experienceBuffer.slice(-100);
  }

  private async loadExperiencesBySource(source: string): Promise<ExperienceEntry[]> {
    // 2026-09-03 Fix③：与 loadExperiences 同口径——优先读库（重启后 buffer 为空，
    // 只读 buffer 会让 distill 永远"无数据可蒸馏"），库为空才回退进程内 buffer。
    let experiences: ExperienceEntry[] = [];
    try {
      const persisted = await this.loadPersistedExperiences({});
      if (persisted.length > 0) experiences = persisted;
    } catch { /* 库不可用时回退 buffer */ }
    if (experiences.length === 0) experiences = this.experienceBuffer.slice(-100);

    // 根据 source 筛选经验
    if (source === 'successful_trades') return experiences.filter(exp => exp.reward > 0);
    if (source === 'failed_trades') return experiences.filter(exp => exp.reward < 0);
    return experiences;
  }

  private minePatterns(experiences: ExperienceEntry[], focus: string): any[] {
    // 简化实现：实际需要更复杂的模式挖掘算法
    const patterns: any[] = [];
    
    // 分组统计
    const groups: Map<string, ExperienceEntry[]> = new Map();
    for (const exp of experiences) {
      const key = exp.tags[0] || 'unknown';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(exp);
    }

    // 生成模式
    for (const [key, group] of groups.entries()) {
      const avgReward = group.reduce((sum, e) => sum + e.reward, 0) / group.length;
      const successRate = group.filter(e => e.outcome.success).length / group.length;
      
      patterns.push({
        pattern_type: key,
        sample_size: group.length,
        avg_reward: avgReward,
        success_rate: successRate,
        insight: `${key}: 成功率 ${(successRate * 100).toFixed(1)}%, 平均奖励 ${avgReward.toFixed(2)}`,
      });
    }

    return patterns;
  }

  private generateImprovements(patterns: any[]): any[] {
    // 基于模式生成改进建议
    return patterns
      .filter(p => p.success_rate < 0.7 || p.avg_reward < 0.3)
      .map(p => ({
        target: p.pattern_type,
        issue: p.success_rate < 0.7 ? '成功率偏低' : '奖励偏低',
        suggestion: `考虑优化 ${p.pattern_type} 的决策逻辑`,
        priority: p.sample_size > 20 ? 'high' : 'medium',
      }));
  }

  private identifyDistillableRules(patterns: any[]): any[] {
    // 识别可蒸馏的规则
    return patterns
      .filter(p => p.success_rate > 0.8 && p.sample_size > 10)
      .map(p => ({
        rule_candidate: p.pattern_type,
        confidence: p.success_rate,
        support: p.sample_size,
        description: `${p.pattern_type} 高成功率模式，可蒸馏为快速规则`,
      }));
  }

  private calculateStatistics(experiences: ExperienceEntry[]): any {
    return {
      total: experiences.length,
      success_rate: experiences.filter(e => e.outcome.success).length / experiences.length,
      avg_reward: experiences.reduce((sum, e) => sum + e.reward, 0) / experiences.length,
      reward_distribution: {
        positive: experiences.filter(e => e.reward > 0).length,
        negative: experiences.filter(e => e.reward < 0).length,
        neutral: experiences.filter(e => e.reward === 0).length,
      },
    };
  }

  private distillRules(options: any): any[] {
    // 蒸馏规则的核心逻辑
    const { experiences, targetFormat, minConfidence, maxRules } = options;
    
    // 简化实现：实际需要更复杂的蒸馏算法（决策树、规则学习等）
    const rules: any[] = [];
    
    // 按 reward 降序排序
    const sorted = [...experiences].sort((a, b) => b.reward - a.reward);
    const topExperiences = sorted.slice(0, Math.min(50, experiences.length));
    
    // 提取共性特征
    for (const exp of topExperiences.slice(0, maxRules)) {
      if (exp.reward > 0 && exp.outcome.success) {
        rules.push({
          id: `rule_${Date.now()}_${rules.length}`,
          condition: this.extractCondition(exp),
          action: this.extractAction(exp),
          confidence: Math.min(0.99, exp.reward + 0.3),
          source_experiences: [exp.id],
          format: targetFormat,
        });
      }
    }
    
    return rules.filter(r => r.confidence >= minConfidence);
  }

  private extractCondition(exp: ExperienceEntry): string {
    // 从经验中提取条件
    const ctx = exp.context;
    return `context matches ${JSON.stringify(ctx)}`;
  }

  private extractAction(exp: ExperienceEntry): string {
    // 从经验中提取行动
    return `execute ${exp.action.tool} with similar params`;
  }

  private getDistillMethod(targetFormat: string): string {
    const methods: Record<string, string> = {
      rules: 'decision_tree_learning',
      code: 'template_based_generation',
      decision_tree: 'CART_algorithm',
      prompt_snippet: 'few_shot_extraction',
    };
    return methods[targetFormat] || 'unknown';
  }

  private validateRules(rules: any[], experiences: ExperienceEntry[]): any {
    // 验证规则在经验集上的表现
    return {
      total_rules: rules.length,
      avg_confidence: rules.length > 0 ? rules.reduce((sum, r) => sum + r.confidence, 0) / rules.length : 0,
      coverage: rules.length > 0 && experiences.length > 0 ? rules.length / experiences.length : 0,
    };
  }

  // 2026-09-03 Fix③：下线死代码 generateChanges/generateRuleChanges/generateParameterChanges/
  // generateCodeChanges/generateConfigChanges/generatePromptChanges/generateValidationPlan/applyChanges
  // （约 L755-834 原实现：全仓库无调用点；applyChanges 仅记日志不做事 = "假成功"反模式）。
  // 真实"应用规则"语义已由 applyRule 重写为规则状态机迁移（testing→active 落库），
  // 见本文件 applyRule / persistDistilledRules 注释。
}

// ===== 类型定义 =====

interface ExperienceEntry {
  id: string;
  timestamp: string;
  agent_version: string;
  action: {
    tool?: string;
    type?: string;
    args?: any;
    context?: any;
  };
  context: any;
  outcome: {
    success: boolean;
    result?: any;
    error?: string;
    duration_ms?: number;
    metrics?: any;
  };
  reward: number;
  reasoning_trace?: string[];
  tags: string[];
  genome_context?: {          // P0-3: 决策打标，归因地基
    genome_version: string;   // 如 g2
    rules_used: string[];     // 如 ["R-001", "R-007"]
  };
}
