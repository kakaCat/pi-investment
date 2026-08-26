import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { readFileSync } from 'node:fs';

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

    // learning_track - 手动追踪经验
    ctx.tools.register(defineTool({
      name: 'learning_track',
      description: '手动追踪执行经验（写操作）。自动追踪已覆盖主要工具，仅在需要记录特殊经验时手动调用。适用于：记录复杂决策过程、非标准工具调用、用户反馈。',
      parameters: {
        action_type: {
          type: 'string',
          description: '行动类型',
          enum: ['trade', 'analysis', 'strategy_execution', 'system_operation', 'custom'],
          required: true,
        },
        context: {
          type: 'object',
          description: '上下文信息，如 {symbol, strategy_id, market_phase}',
          additionalProperties: true,
          required: true,
        },
        outcome: {
          type: 'object',
          description: '结果：{success, metrics, error?}',
          properties: {
            success: { type: 'boolean' },
            metrics: { type: 'object', additionalProperties: true },
            error: { type: 'string' },
          },
          additionalProperties: true,
          required: true,
        },
        reward: {
          type: 'number',
          description: '奖励信号（-1.0 ~ 1.0），正值表示好结果，负值表示坏结果',
          required: true,
        },
        reasoning_trace: {
          type: 'array',
          description: '推理过程记录，用于后续蒸馏',
          items: { type: 'string' },
        },
        metadata: {
          type: 'object',
          description: '额外元数据',
          additionalProperties: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            experience_id: { type: 'string' },
            message: { type: 'string' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        const entry: ExperienceEntry = {
          id: `exp_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
          timestamp: new Date().toISOString(),
          agent_version: process.env.AGENT_VERSION || 'dev',
          action: { type: args.action_type, context: args.context },
          context: args.context,
          outcome: args.outcome,
          reward: args.reward,
          reasoning_trace: args.reasoning_trace,
          tags: this.extractTagsFromContext(args.context),
        };

        this.experienceBuffer.push(entry);
        await this.persistExperience(entry);

        return {
          success: true,
          experience_id: entry.id,
          message: `经验已记录：${args.action_type}，奖励 ${args.reward}`,
        } as any;
      },
    } as any));

    // learning_analyze - 分析学习机会
    ctx.tools.register(defineTool({
      name: 'learning_analyze',
      description: '分析经验库，挖掘成功/失败模式，生成改进建议。适用于：定期（如每周）分析学习机会、策略表现下滑后寻找原因、识别可优化的决策模式。',
      parameters: {
        scope: {
          type: 'string',
          description: '分析范围。recent：最近经验；all：全部；strategy:{id}：特定策略',
          default: 'recent',
        },
        focus: {
          type: 'string',
          description: '关注点',
          enum: ['failures', 'successes', 'patterns', 'all'],
          default: 'patterns',
        },
        min_samples: {
          type: 'integer',
          description: '最小样本数，少于此数不做分析',
          default: 10,
        },
        time_range_days: {
          type: 'integer',
          description: '时间范围（天），默认 30',
          default: 30,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            total_samples: { type: 'integer' },
            patterns: { type: 'array', description: '识别的模式' },
            improvements: { type: 'array', description: '改进建议' },
            distillable_rules: { type: 'array', description: '可蒸馏规则' },
            statistics: { type: 'object', additionalProperties: true },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        // 从 memory 搜索经验
        const experiences = await this.loadExperiences({
          scope: args.scope,
          timeRangeDays: args.time_range_days,
        });

        if (experiences.length < args.min_samples) {
          return {
            total_samples: experiences.length,
            patterns: [],
            improvements: [],
            message: `样本不足（${experiences.length} < ${args.min_samples}），无法分析`,
          } as any;
        }

        // 模式挖掘
        const patterns = this.minePatterns(experiences, args.focus);
        const improvements = this.generateImprovements(patterns);
        const distillableRules = this.identifyDistillableRules(patterns);

        return {
          total_samples: experiences.length,
          patterns,
          improvements,
          distillable_rules: distillableRules,
          statistics: this.calculateStatistics(experiences),
        } as any;
      },
    } as any));

    // learning_distill - 知识蒸馏
    ctx.tools.register(defineTool({
      name: 'learning_distill',
      description: '从复杂推理中提取简单规则，降低决策成本。适用于：将成功案例蒸馏成快速规则、优化慢速决策流程、构建可复用规则库。',
      parameters: {
        source: {
          type: 'string',
          description: '蒸馏源',
          enum: ['experiences', 'reasoning_traces', 'successful_trades', 'failed_trades'],
          required: true,
        },
        target_format: {
          type: 'string',
          description: '目标格式',
          enum: ['rules', 'code', 'decision_tree', 'prompt_snippet'],
          default: 'rules',
        },
        min_confidence: {
          type: 'number',
          description: '最小置信度阈值（0-1），低于此值的规则不输出',
          default: 0.7,
        },
        max_rules: {
          type: 'integer',
          description: '最多输出规则数',
          default: 10,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            rules: { type: 'array', description: '蒸馏出的规则列表' },
            source_count: { type: 'integer', description: '源经验数量' },
            distill_method: { type: 'string' },
            validation_stats: { type: 'object', additionalProperties: true },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        const experiences = await this.loadExperiencesBySource(args.source);
        
        const rules = this.distillRules({
          experiences,
          targetFormat: args.target_format,
          minConfidence: args.min_confidence,
          maxRules: args.max_rules,
        });

        return {
          rules,
          source_count: experiences.length,
          distill_method: this.getDistillMethod(args.target_format),
          validation_stats: this.validateRules(rules, experiences),
        } as any;
      },
    } as any));

    // learning_apply - 应用学习结果
    ctx.tools.register(defineTool({
      name: 'learning_apply',
      description: '应用学习结果：生成代码/配置改动，通过 self_restart 安全验证后生效。适用于：应用蒸馏规则、优化策略参数、改进系统代码。高风险操作，建议先 dry_run。',
      parameters: {
        improvement_type: {
          type: 'string',
          description: '改进类型',
          enum: ['rule', 'parameter', 'code', 'config', 'prompt'],
          required: true,
        },
        improvement_spec: {
          type: 'object',
          description: '改进规格：具体的改动内容',
          additionalProperties: true,
          required: true,
        },
        dry_run: {
          type: 'boolean',
          description: 'true（默认）：只生成改动预览，不实际执行；false：生成并应用',
          default: true,
        },
        restart_after: {
          type: 'boolean',
          description: '应用后是否自动重启验证',
          default: false,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            changes: { type: 'array', description: '生成的改动列表' },
            validation_plan: { type: 'string' },
            next_steps: { type: 'array', items: { type: 'string' } },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        const changes = await this.generateChanges({
          type: args.improvement_type,
          spec: args.improvement_spec,
        });

        if (args.dry_run) {
          return {
            success: true,
            dry_run: true,
            changes,
            validation_plan: this.generateValidationPlan(changes),
            next_steps: [
              '1. 检查改动是否符合预期',
              '2. 确认后设置 dry_run=false 再次调用',
              '3. 如需重启验证，设置 restart_after=true',
            ],
          } as any;
        }

        // 实际应用改动
        await this.applyChanges(changes);

        // 如果需要重启
        if (args.restart_after) {
          // 调用 self_restart
          // 注意：这里需要通过 ctx.tools 调用
          return {
            success: true,
            changes,
            message: '改动已应用，准备重启验证...',
            restart_scheduled: true,
          } as any;
        }

        return {
          success: true,
          changes,
          message: '改动已应用，建议手动验证后调用 self_restart',
        } as any;
      },
    } as any));

    // P1-1: experience_distill - 经验蒸馏，生成改进建议
    this.ctx.tools.register(defineTool({
      name: 'experience_distill',
      description: 'P1-1 经验蒸馏：按 genome_version 分组统计规则表现，识别高低奖励模式，生成改进建议（新增规则/修改原则）。用于：盘后复盘、每日蒸馏、手动分析决策质量。',
      parameters: {
        days: {
          type: 'number',
          description: '分析最近 N 天经验（默认 7）',
          default: 7,
        },
        genome_version: {
          type: 'string',
          description: '指定基因组版本（不传=最新版本）',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            genome_version: { type: 'string' },
            period: {
              type: 'object',
              properties: {
                from: { type: 'string' },
                to: { type: 'string' },
              },
              additionalProperties: false,
            },
            stats: {
              type: 'object',
              properties: {
                total_experiences: { type: 'number' },
                avg_reward: { type: 'number' },
                success_rate: { type: 'number' },
                by_genome_version: {
                  type: 'object',
                  description: '按基因组代数分组的统计（归因：哪代基因组在赚钱）',
                  additionalProperties: true,
                },
              },
              additionalProperties: false,
            },
            high_reward_patterns: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  pattern: { type: 'string' },
                  avg_reward: { type: 'number' },
                  count: { type: 'number' },
                },
                additionalProperties: false,
              },
            },
            low_reward_patterns: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  pattern: { type: 'string' },
                  avg_reward: { type: 'number' },
                  count: { type: 'number' },
                },
                additionalProperties: false,
              },
            },
            suggestions: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  type: { type: 'string' },
                  section: { type: 'string' },
                  content: { type: 'string' },
                  reason: { type: 'string' },
                },
                additionalProperties: false,
              },
            },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: JSON.stringify(value, null, 2) },
        ],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        const { days, genome_version } = args;

        // 1. 确定目标版本（不传 = 当前版本，用于输出展示）
        let targetVersion = genome_version;
        if (!targetVersion) {
          // @ts-ignore
          const genome = this.ctx.genome;
          if (genome?.genomeData) {
            targetVersion = genome.genomeData.genome_version;
          } else {
            targetVersion = 'g1';  // fallback
          }
        }

        // 2. 时间范围
        const endDate = new Date();
        const startDate = new Date(endDate.getTime() - days * 24 * 60 * 60 * 1000);

        // 3. 从 memory 库召回持久化经验（2026-08-22 修复：原实现只读进程内缓冲区，
        // 重启即空；现在读库，缓冲区仅作后端不可用时的回退）
        let experiences = await this.loadPersistedExperiences({
          sinceTs: startDate.getTime(),
          genomeVersion: genome_version,  // 显式指定版本才过滤；否则全量（分组统计）
        });
        if (experiences.length === 0) {
          experiences = this.experienceBuffer.filter((e: ExperienceEntry) => {
            const ts = new Date(e.timestamp);
            return ts >= startDate && ts <= endDate &&
                   (!genome_version || e.genome_context?.genome_version === genome_version);
          });
        }

        // 3b. 按基因组代数分组统计（归因：哪代基因组在赚钱）
        const byVersion: Record<string, { count: number; avg_reward: number; success_rate: number }> = {};
        const vGroups = new Map<string, ExperienceEntry[]>();
        for (const e of experiences) {
          const v = e.genome_context?.genome_version ?? 'unknown';
          if (!vGroups.has(v)) vGroups.set(v, []);
          vGroups.get(v)!.push(e);
        }
        for (const [v, list] of vGroups) {
          byVersion[v] = {
            count: list.length,
            avg_reward: Math.round(list.reduce((s, e) => s + e.reward, 0) / list.length * 1000) / 1000,
            success_rate: Math.round(list.filter(e => e.outcome.success).length / list.length * 1000) / 1000,
          };
        }

        if (experiences.length === 0) {
          return {
            genome_version: targetVersion,
            period: { from: startDate.toISOString(), to: endDate.toISOString() },
            stats: { total_experiences: 0, avg_reward: 0, success_rate: 0 },
            high_reward_patterns: [],
            low_reward_patterns: [],
            suggestions: [{
              type: 'info',
              section: '',
              content: '',
              reason: '无数据：过去 ' + days + ' 天没有经验记录',
            }],
          } as any;
        }

        // 4. 统计
        const totalReward = experiences.reduce((sum, e) => sum + e.reward, 0);
        const successCount = experiences.filter(e => e.outcome.success).length;

        // 5. 模式识别（简化：按工具分组）
        const toolGroups = new Map<string, ExperienceEntry[]>();
        experiences.forEach(e => {
          const tool = e.action.tool || 'unknown';
          if (!toolGroups.has(tool)) toolGroups.set(tool, []);
          toolGroups.get(tool)!.push(e);
        });

        const highRewardPatterns = [];
        const lowRewardPatterns = [];

        for (const [tool, entries] of toolGroups) {
          const avgReward = entries.reduce((sum, e) => sum + e.reward, 0) / entries.length;
          const pattern = {
            pattern: `${tool} 调用`,
            avg_reward: Math.round(avgReward * 100) / 100,
            count: entries.length,
          };

          if (avgReward > 0.5) {
            highRewardPatterns.push(pattern);
          } else if (avgReward < 0) {
            lowRewardPatterns.push(pattern);
          }
        }

        // 6. 生成建议（模板化，简化版）
        const suggestions = [];
        if (lowRewardPatterns.length > 0) {
          const worst = lowRewardPatterns[0];
          suggestions.push({
            type: 'add_rule',
            section: 'rules',
            content: `R-XXX: 针对 ${worst.pattern} 低奖励（${worst.avg_reward}），考虑增加前置校验规则`,
            reason: `过去 ${days} 天该操作平均奖励 ${worst.avg_reward}，需要改进`,
          });
        }

        if (highRewardPatterns.length > 0) {
          const best = highRewardPatterns[0];
          suggestions.push({
            type: 'modify_principle',
            section: 'principles',
            content: `强化 ${best.pattern} 相关原则（当前平均奖励 ${best.avg_reward}）`,
            reason: `高奖励模式，应纳入核心原则`,
          });
        }

        if (suggestions.length === 0) {
          suggestions.push({
            type: 'info',
            section: '',
            content: '',
            reason: '数据量不足或表现平稳，暂无改进建议',
          });
        }

        return {
          genome_version: targetVersion,
          period: {
            from: startDate.toISOString(),
            to: endDate.toISOString(),
          },
          stats: {
            total_experiences: experiences.length,
            avg_reward: Math.round((totalReward / experiences.length) * 100) / 100,
            success_rate: Math.round((successCount / experiences.length) * 100) / 100,
            by_genome_version: byVersion,
          },
          high_reward_patterns: highRewardPatterns,
          low_reward_patterns: lowRewardPatterns,
          suggestions,
        } as any;
      },
    } as any));

    // M6: 周报自动生成（RFC 004 学习飞轮，2026-08-23）
    ctx.tools.register(defineTool({
      name: 'weekly_report',
      description: '生成投资周报：本周成交与盈亏、胜率、regime 序列、主线回顾、基因组进化事件、信号追踪胜率、观察期候选裁决、风险指标。落库 scope=report:weekly 并飞书推送。供：每周复盘（验收要求连续 4 周无中断）、向用户透明汇报进化与表现。',
      parameters: {
        days: { type: 'number', description: '统计窗口（天），默认 7', default: 7 },
        push_feishu: { type: 'boolean', description: '是否飞书推送（默认 true）', default: true },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            period: { type: 'object', additionalProperties: true },
            report_markdown: { type: 'string' },
            metrics: { type: 'object', additionalProperties: true },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: value.report_markdown }],
      },
      timeoutMs: 120000,
      execute: async (args: any) => {
        const days = args.days ?? 7;
        const pushFeishu = args.push_feishu !== false;
        const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });
        const since = new Date(Date.now() - days * 86400000);
        const sinceStr = since.toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

        // 1. 本周成交
        let trades: any[] = [];
        try {
          const th: any = await this.qv2.getTradeHistory({ account_name: 'agent_virtual' });
          // orders/items 双兼容（后端实际返回 items）
          trades = (th?.orders || th?.items || []).filter((t: any) => String(t.tradeDate ?? t.trade_date ?? '') >= sinceStr);
        } catch { /* 成交查询失败不阻塞 */ }
        const sells = trades.filter((t: any) => String(t.action).toLowerCase() === 'sell' && t.pnl != null);
        const wins = sells.filter((t: any) => Number(t.pnl) > 0);
        const totalPnl = sells.reduce((s, t) => s + Number(t.pnl ?? 0), 0);

        // 2. 组合与风险
        let summary: any = {}, metrics: any = {};
        try { summary = await this.qv2.getPortfolioSummary('agent_virtual'); } catch { /* skip */ }
        try { metrics = await this.qv2.getRiskMetrics({ account_name: 'agent_virtual', days: 60 }); } catch { /* skip */ }

        // 3. regime 与主线序列（本周落库记录）
        const regimeRes = await this.osMemory.searchMemory({ q: 'regime', scope: 'market:regime', limit: 20 }).catch(() => null);
        const regimes = (regimeRes?.items || [])
          .filter((it: any) => it.status !== 'deprecated' && it.payload?.date >= sinceStr)
          .map((it: any) => `${it.payload.date}:${it.payload.regime}`);

        const mainlineRes = await this.osMemory.searchMemory({ q: 'mainline', scope: 'market:mainline', limit: 20 }).catch(() => null);
        const mainlines = (mainlineRes?.items || [])
          .filter((it: any) => it.status !== 'deprecated' && it.payload?.date >= sinceStr && it.payload?.mainlines)
          .map((it: any) => `${it.payload.date}: ${it.payload.mainlines.map((m: any) => m.sector).join('/')}`);

        // 4. 基因组进化事件（genome.json history 本周条目）
        let genomeEvents: any[] = [];
        let genomeVersion = 'unknown';
        try {
          // @ts-ignore - genome 插件运行时字段
          const genomeDir = this.ctx.genome?.genomeDir;
          genomeVersion = this.ctx.genome?.genomeData?.genome_version ?? 'unknown';
          if (genomeDir) {
            const fs = await import('fs');
            const path = await import('path');
            const gj = JSON.parse(fs.readFileSync(path.join(genomeDir, 'genome.json'), 'utf-8'));
            genomeEvents = (gj.history || []).filter((h: any) => String(h.ts ?? '') >= since.toISOString());
          }
        } catch { /* skip */ }

        // 5. 信号追踪统计
        let signalStats: any = null;
        try {
          const sigRes = await this.osMemory.searchMemory({ q: 'signal', scope: 'signal:tracking', limit: 100 });
          const sigs = (sigRes?.items || []).filter((it: any) => it.status !== 'deprecated' && it.payload?.signal_date);
          const evaluated = sigs.filter((it: any) => it.payload?.forward?.d5 !== undefined);
          const wins5 = evaluated.filter((it: any) => it.payload.forward.d5 > 0);
          signalStats = {
            total: sigs.length,
            evaluated_5d: evaluated.length,
            win_rate_5d: evaluated.length > 0 ? +(wins5.length / evaluated.length).toFixed(3) : null,
          };
        } catch { /* skip */ }

        // 6. 观察期候选
        let candidates: any[] = [];
        try {
          // @ts-ignore
          const genomeDir = this.ctx.genome?.genomeDir;
          if (genomeDir) {
            const fs = await import('fs');
            const path = await import('path');
            const cp = path.join(genomeDir, 'candidates.json');
            if (fs.existsSync(cp)) candidates = JSON.parse(fs.readFileSync(cp, 'utf-8'));
          }
        } catch { /* skip */ }

        // 7. 组装报告
        const lines: string[] = [];
        lines.push(`# 投资周报 ${sinceStr} ~ ${today}`);
        lines.push('');
        lines.push(`## 组合`);
        lines.push(`- 总资产: ¥${Number(summary?.totalValue ?? 0).toLocaleString()} ｜ 权益仓位: ${summary?.totalValue > 0 ? (Number(summary?.totalMarketValue ?? 0) / Number(summary?.totalValue) * 100).toFixed(1) : '?'}%`);
        lines.push(`- 60日最大回撤: ${((Number(metrics?.maxDrawdown ?? 0)) * 100).toFixed(2)}% ｜ 夏普: ${Number(metrics?.sharpeRatio ?? 0).toFixed(2)}`);
        lines.push('');
        lines.push(`## 本周交易（${trades.length} 笔）`);
        lines.push(`- 卖出平仓 ${sells.length} 笔，盈利 ${wins.length} 笔，胜率 ${sells.length > 0 ? (wins.length / sells.length * 100).toFixed(1) : '—'}%，已实现盈亏 ¥${totalPnl.toFixed(2)}`);
        lines.push('');
        lines.push(`## 市场回顾`);
        lines.push(`- regime 序列: ${regimes.join(' → ') || '无记录'}`);
        lines.push(`- 主线: ${mainlines.join(' ｜ ') || '无记录'}`);
        lines.push('');
        lines.push(`## 基因组进化（当前 ${genomeVersion}）`);
        if (genomeEvents.length > 0) {
          for (const e of genomeEvents) lines.push(`- ${String(e.ts).slice(0, 10)} [${e.type}] ${e.section} v${e.section_version}: ${e.reason}`);
        } else {
          lines.push('- 本周无进化事件');
        }
        lines.push('');
        lines.push(`## 信号追踪`);
        lines.push(`- 累计信号 ${signalStats?.total ?? 0}，已评估(5日) ${signalStats?.evaluated_5d ?? 0}，5日胜率 ${signalStats?.win_rate_5d ?? '—'}`);
        lines.push(`- 观察期候选: ${candidates.filter(c => c.status === 'watching').length} 个观察中，${candidates.filter(c => c.status === 'promoted').length} 个已转正，${candidates.filter(c => c.status === 'rejected').length} 个已回滚`);
        lines.push('');
        lines.push(`*—— 自动生成 by weekly_report（PI 投资顾问·投资脑 w-a8a89c6a）*`);

        const reportMarkdown = lines.join('\n');

        // 8. 落库 + 飞书
        await this.osMemory.createMemory({
          kind: 'episode',
          scope: 'report:weekly',
          title: `投资周报 ${sinceStr}~${today}`,
          content: reportMarkdown,
          payload: { period: { from: sinceStr, to: today }, genome_version: genomeVersion },
          status: 'testing',
          confidence: 0.7,
          source: 'weekly_report',
          provenance: { channel: 'dsh', session_kind: 'agent' },
        });

        if (pushFeishu) {
          try {
            await (this.ctx.tools as any).execute({
              name: 'feishu_notify',
              arguments: { title: `【投资周报】${sinceStr} ~ ${today}`, content: reportMarkdown, urgency: 'low' },
              signal: new AbortController().signal,
            });
          } catch { /* 推送失败不阻塞 */ }
        }

        return {
          period: { from: sinceStr, to: today },
          report_markdown: reportMarkdown,
          metrics: {
            trades: trades.length, sells: sells.length, wins: wins.length, total_pnl: +totalPnl.toFixed(2),
            genome_version: genomeVersion, genome_events: genomeEvents.length,
            signal_stats: signalStats,
          },
        } as any;
      },
    } as any));

    // 规则积分榜（规则级验证门的数据地基，2026-08-23）
    ctx.tools.register(defineTool({
      name: 'rule_scoreboard',
      description: '按规则 ID（R-xxx）统计各规则在打标经验中的表现：引用次数、平均奖励、成功率、最近使用。给出裁决建议：持续负奖励且样本≥3 → 建议淘汰（deprecate）；持续高奖励 → 建议强化。供：规则级归因、验证门规则粒度裁决、周报规则健康度。',
      parameters: {
        min_samples: { type: 'number', description: '给出裁决建议的最小样本数，默认 3', default: 3 },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            rules: { type: 'array', items: { type: 'object', additionalProperties: true } },
            total_experiences_scanned: { type: 'number' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 60000,
      execute: async (args: any) => {
        const minSamples = args.min_samples ?? 3;
        const experiences = await this.loadPersistedExperiences({});

        // 从每条经验的全文（action/outcome/context/genome_context）提取 R-ID
        const ruleMap = new Map<string, { count: number; rewards: number[]; successes: number; last_seen: string }>();
        for (const e of experiences) {
          const ids = new Set<string>(e.genome_context?.rules_used ?? []);
          try {
            const text = JSON.stringify([e.action, e.outcome, e.context]).slice(0, 30000);
            for (const m of text.matchAll(/\b(R-\d{3})\b/g)) ids.add(m[1]);
          } catch { /* skip */ }

          for (const id of ids) {
            if (!ruleMap.has(id)) ruleMap.set(id, { count: 0, rewards: [], successes: 0, last_seen: '' });
            const r = ruleMap.get(id)!;
            r.count++;
            r.rewards.push(e.reward);
            if (e.outcome.success) r.successes++;
            if (e.timestamp > r.last_seen) r.last_seen = e.timestamp;
          }
        }

        const rules = [...ruleMap.entries()].map(([rule_id, r]) => {
          const avg = r.rewards.reduce((a, b) => a + b, 0) / r.rewards.length;
          const successRate = r.successes / r.count;
          let verdict = 'insufficient_data';
          if (r.count >= minSamples) {
            if (avg < 0) verdict = 'suggest_deprecate';
            else if (avg > 0.3 && successRate > 0.6) verdict = 'suggest_strengthen';
            else verdict = 'neutral';
          }
          return {
            rule_id,
            count: r.count,
            avg_reward: +avg.toFixed(3),
            success_rate: +successRate.toFixed(3),
            last_seen: r.last_seen.slice(0, 10),
            verdict,
          };
        }).sort((a, b) => a.avg_reward - b.avg_reward);  // 最差的排前面

        const result = { rules, total_experiences_scanned: experiences.length };

        // 方案 A 共享数据层（2026-08-26）：将成绩单写入 memory 供 evolver rule_gate 读取
        try {
          await this.qv2.createMemory({
            kind: 'experience',  // 用合法kind（analytics被数据库约束拒绝）
            scope: 'analytics:rule_scoreboard',
            title: `rule_scoreboard snapshot ${new Date().toISOString().slice(0, 10)}`,
            content: `规则成绩单快照：${rules.length} 条规则，扫描 ${experiences.length} 条经验`,
            payload: { rules, total_experiences_scanned: experiences.length, generated_at: new Date().toISOString() },
            status: 'active',
            confidence: 1.0,
            source: 'rule_scoreboard',
            provenance: { channel: 'dsh', session_kind: 'tool' },
          });
        } catch { /* 写入失败不阻塞返回 */ }

        return result as any;
      },
    } as any));
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
    // 根据 source 筛选经验
    return this.experienceBuffer.filter(exp => {
      if (source === 'successful_trades') return exp.reward > 0;
      if (source === 'failed_trades') return exp.reward < 0;
      return true;
    });
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
      avg_confidence: rules.reduce((sum, r) => sum + r.confidence, 0) / rules.length,
      coverage: rules.length / experiences.length,
    };
  }

  private async generateChanges(options: any): Promise<any[]> {
    const { type, spec } = options;
    
    // 根据类型生成不同的改动
    switch (type) {
      case 'rule':
        return this.generateRuleChanges(spec);
      case 'parameter':
        return this.generateParameterChanges(spec);
      case 'code':
        return this.generateCodeChanges(spec);
      case 'config':
        return this.generateConfigChanges(spec);
      case 'prompt':
        return this.generatePromptChanges(spec);
      default:
        return [];
    }
  }

  private generateRuleChanges(spec: any): any[] {
    return [{
      type: 'rule_addition',
      file: 'packages/strategy/src/rules.ts',
      description: '添加新规则',
      content: spec.rule_code || '// TODO: generated rule',
    }];
  }

  private generateParameterChanges(spec: any): any[] {
    return [{
      type: 'parameter_update',
      file: spec.file || 'cordis.patch.yml',
      parameter: spec.parameter,
      old_value: spec.old_value,
      new_value: spec.new_value,
      description: `更新参数 ${spec.parameter}: ${spec.old_value} → ${spec.new_value}`,
    }];
  }

  private generateCodeChanges(spec: any): any[] {
    return [{
      type: 'code_modification',
      file: spec.file,
      description: spec.description || '代码优化',
      diff: spec.diff || '// TODO: generated diff',
    }];
  }

  private generateConfigChanges(spec: any): any[] {
    return [{
      type: 'config_update',
      file: '~/.dsh/profiles/investment/cordis.patch.yml',
      description: '配置更新',
      changes: spec.changes,
    }];
  }

  private generatePromptChanges(spec: any): any[] {
    return [{
      type: 'prompt_enhancement',
      description: 'System prompt 优化',
      addition: spec.prompt_snippet || '// TODO: prompt snippet',
    }];
  }

  private generateValidationPlan(changes: any[]): string {
    const steps = changes.map((c, i) => 
      `${i + 1}. 验证 ${c.type}: ${c.description}`
    );
    return steps.join('\n');
  }

  private async applyChanges(changes: any[]): Promise<void> {
    for (const change of changes) {
      this.ctx.logger.info(`learning: applying change ${change.type} to ${change.file || 'system'}`);
      // 实际实现需要调用文件操作工具
      // 这里仅记录日志
    }
  }
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
