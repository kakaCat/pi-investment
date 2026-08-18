import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { AgentOSClient } from '@pi-investment/agent-os-client';

export interface Config {
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

/**
 * Memory Plugin for Agent-DH
 *
 * Long-term memory storage and retrieval via Agent OS.
 */
export default class MemoryPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any)

  private aos: AgentOSClient;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'memory');
    this.aos = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
      agentId: config.agentOS?.agentId || 'agent-dh',
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, aos } = this;

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
      timeoutMs: 10000,
      execute: async (args: any) => {
        return aos.memory.search({
          namespace: args.namespace || 'default',
          query: args.query,
          top_k: args.top_k || 5,
        }) as any;
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
      timeoutMs: 10000,
      execute: async (args: any) => {
        return aos.memory.write({
          namespace: args.namespace || 'default',
          content: args.content,
          importance: args.importance || 0.5,
          tags: args.tags,
        }) as any;
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
      timeoutMs: 10000,
      execute: async (args: any) => {
        return aos.memory.write({
          namespace: 'experience',
          content: JSON.stringify({
            symbol: args.symbol,
            scenario: args.scenario,
            outcome: args.outcome,
            lesson: args.lesson,
            pnl_pct: args.pnl_pct,
            timestamp: new Date().toISOString(),
          }),
          importance: args.outcome === 'loss' ? 0.8 : 0.6,
          tags: [args.symbol, args.outcome, 'experience'],
        }) as any;
      },
    } as any));
  }
}
