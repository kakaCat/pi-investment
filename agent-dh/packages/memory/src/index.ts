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
      description: '搜索长期记忆，找回历史分析、决策和经验。用于：查找之前对某只股票的分析、回顾历史决策理由、获取经验教训',
      parameters: {
        query: {
          type: 'string',
          description: '搜索关键词，如：贵州茅台、2024年Q1、止损经验',
          required: true,
        },
        top_k: {
          type: 'integer',
          description: '返回结果数量，默认5条',
          default: 5,
        },
        namespace: {
          type: 'string',
          description: '记忆命名空间：default（默认）、experience（经验）、decision（决策）、analysis（分析）',
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
        render: (_args, value) => [{
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
      description: '写入长期记忆，保存重要分析结论、经验教训。用于：记录有价值的分析、保存决策理由以便后续复盘',
      parameters: {
        content: {
          type: 'string',
          description: '记忆内容，建议结构化描述，如："600贵州茅台：2024Q3营收增长15%，主要驱动来自系列酒放量，需关注渠道库存"',
          required: true,
        },
        importance: {
          type: 'number',
          description: '重要程度（0-1），0.3=普通记录，0.5=重要，0.8=关键决策依据',
          default: 0.5,
        },
        namespace: {
          type: 'string',
          description: '记忆命名空间：default、experience、decision、analysis',
          default: 'default',
        },
        tags: {
          type: 'array',
          description: '标签列表，如：["600519", "白酒", "Q3财报"]',
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
        render: (_args, value) => [{
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
      description: '记录交易经验，用于后续策略优化。用于：记录每笔交易的得失原因，形成可复用的经验库',
      parameters: {
        symbol: {
          type: 'string',
          description: '股票代码，如：600519',
          required: true,
        },
        scenario: {
          type: 'string',
          description: '场景描述，如："突破买入后遭遇大盘回调"',
          required: true,
        },
        outcome: {
          type: 'string',
          description: '结果：profit（盈利）、loss（亏损）、neutral（持平）',
          enum: ['profit', 'loss', 'neutral'],
        },
        lesson: {
          type: 'string',
          description: '经验教训，如："突破买入需确认大盘趋势，单边下跌市慎用"',
        },
        pnl_pct: {
          type: 'number',
          description: '盈亏比例（%），如：15.5 或 -8.2',
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
        render: (_args, value) => [{
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
