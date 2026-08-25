import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
  /** 已废弃：历史 agent-os 配置，仅为兼容旧配置文件保留，不再使用 */
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

/**
 * Memory Plugin for Agent-DH
 *
 * Long-term memory storage and retrieval via Agent OS 记忆库
 * （2026-08-25 起：quantsys-v2 记忆库写入停用，统一迁移 Agent OS /api/v1/memory，
 *  postgres 持久；经 @pi-investment/os-memory 适配器，title+content 文本检索）。
 *
 * 2026-08-19: 从已废弃的 agent-os 客户端迁移到 quantsys-v2。
 * 2026-08-25: quantsys-v2 记忆库写入挂起（ollama embedding 超时），迁回 Agent OS。
 */
export default class MemoryPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;
  private osMemory: OsMemoryStore;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'memory');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    // 2026-08-25：quantsys-v2 记忆库写入停用，记忆读写迁 Agent OS
    this.osMemory = new OsMemoryStore({ baseURL: (config as any).agentOS?.baseURL || 'http://localhost:8080', agentId: (config as any).agentOS?.agentId || 'agent-dh' });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 记忆搜索
    ctx.tools.register(defineTool({
      name: 'memory_search',
      description: '语义搜索长期记忆，找回历史分析结论、决策理由、经验教训。适用于：分析某只股票前查是否已分析过、复盘历史决策、复用过往经验。记忆由 memory_write / experience_write 写入，写入越规范检索越准。',
      parameters: {
        query: {
          type: 'string',
          description: '搜索内容，支持自然语言或关键词，如 "贵州茅台"、"止损经验"、"2024Q1 白酒"',
          required: true,
        },
        top_k: {
          type: 'integer',
          description: '返回最相关的结果条数，默认 5。结果不全时可增大',
          default: 5,
        },
        namespace: {
          type: 'string',
          description: '记忆命名空间。default（默认）：通用记忆；experience：交易经验（experience_write 写入）；decision：决策记录；analysis：分析结论',
          default: 'default',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            query: { type: 'string', description: '搜索关键词' },
            results: { type: 'array', description: '记忆条目列表' },
            total: { type: 'integer', description: '总匹配数' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        const namespace = args.namespace || 'default';
        const res = await this.osMemory.searchMemory({
          q: args.query,
          limit: args.top_k || 5,
          // experience 命名空间对应后端 kind=experience；其余命名空间不做 kind 过滤
          kind: namespace === 'experience' ? 'experience' : undefined,
        });
        // embedding 向量为千维数组，剔除以避免污染上下文
        const items = (res.items || []).map((it: any) => {
          const { embedding, ...rest } = it ?? {};
          return rest;
        });
        return {
          query: args.query,
          results: items,
          total: res.total ?? items.length,
          degraded: res.degraded,
          strategy: res.strategy,
        } as any;
      },
    } as any));

    // 记忆写入
    ctx.tools.register(defineTool({
      name: 'memory_write',
      description: '写入长期记忆（写操作），保存分析结论、决策依据，供未来 memory_search 检索复用。适用于：完成重要分析后沉淀结论、记录决策理由以便复盘。记录交易得失经验请用 experience_write（结构更专门）。内容建议结构化并包含股票代码和时间，便于检索。',
      parameters: {
        content: {
          type: 'string',
          description: '记忆内容。建议结构化描述并含关键实体，如 "600519贵州茅台：2024Q3营收增长15%，驱动来自系列酒放量，需关注渠道库存"',
          required: true,
        },
        importance: {
          type: 'number',
          description: '重要程度 0-1，默认 0.5。参考：0.3 普通记录；0.5 重要；0.8 关键决策依据。重要性影响后续检索排序',
          default: 0.5,
        },
        namespace: {
          type: 'string',
          description: '记忆命名空间：default（默认）、experience、decision、analysis，与 memory_search 的 namespace 对应',
          default: 'default',
        },
        tags: {
          type: 'array',
          description: '标签列表，如 ["600519", "白酒", "Q3财报"]，用于提升检索命中率',
          items: { type: 'string' },
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean', description: '是否成功' },
            memory_id: { type: 'string', description: '记忆ID' },
            message: { type: 'string', description: '结果消息' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        const namespace = args.namespace || 'default';
        const content = String(args.content);
        const res = await this.osMemory.createMemory({
          kind: namespace === 'experience' ? 'experience' : 'episode',
          scope: 'global',
          title: content.slice(0, 50),
          content,
          payload: { namespace, tags: args.tags || [] },
          // 无证据链时后端门禁要求 status=testing
          status: 'testing',
          confidence: typeof args.importance === 'number' ? args.importance : 0.5,
          source: 'agent',
          provenance: { channel: 'dsh', session_kind: 'agent' },
        });
        return {
          success: true,
          memory_id: String(res?.id ?? ''),
          message: '已写入 quantsys-v2 统一记忆库（status=testing，混合检索可召回）',
        } as any;
      },
    } as any));

    // 经验写入
    ctx.tools.register(defineTool({
      name: 'experience_write',
      description: '记录一笔交易的经验教训（写操作，写入 experience 命名空间；亏损记录自动标记更高重要性）。适用于：平仓或阶段复盘后沉淀得失原因，形成可复用的经验库，供后续决策时通过 memory_search(namespace=experience) 检索。一般性的分析结论用 memory_write。',
      parameters: {
        symbol: {
          type: 'string',
          description: '股票代码，如 600519',
          required: true,
        },
        scenario: {
          type: 'string',
          description: '当时的市场场景与操作，如 "突破买入后遭遇大盘回调"',
          required: true,
        },
        outcome: {
          type: 'string',
          description: '结果。profit：盈利；loss：亏损（自动提高重要性权重）；neutral：持平',
          enum: ['profit', 'loss', 'neutral'],
        },
        lesson: {
          type: 'string',
          description: '提炼的经验教训，如 "突破买入需确认大盘趋势，单边下跌市慎用"',
        },
        pnl_pct: {
          type: 'number',
          description: '盈亏比例（%），如 15.5 或 -8.2',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean', description: '是否成功' },
            experience_id: { type: 'string', description: '经验ID' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        const timestamp = new Date().toISOString();
        const content = [
          `${args.symbol} 交易经验（${timestamp}）`,
          `场景：${args.scenario}`,
          args.outcome ? `结果：${args.outcome}` : null,
          typeof args.pnl_pct === 'number' ? `盈亏：${args.pnl_pct}%` : null,
          args.lesson ? `教训：${args.lesson}` : null,
        ].filter(Boolean).join('\n');
        const res = await this.osMemory.createMemory({
          kind: 'experience',
          scope: `stock:${args.symbol}`,
          title: `${args.symbol} ${args.outcome || ''} ${args.scenario}`.slice(0, 80),
          content,
          payload: {
            symbol: args.symbol,
            outcome: args.outcome,
            lesson: args.lesson,
            pnl_pct: args.pnl_pct,
            timestamp,
          },
          status: 'testing',
          confidence: args.outcome === 'loss' ? 0.8 : 0.6,
          source: 'agent',
          provenance: { channel: 'dsh', session_kind: 'agent' },
        });
        return {
          success: true,
          experience_id: String(res?.id ?? ''),
        } as any;
      },
    } as any));
  }
}
