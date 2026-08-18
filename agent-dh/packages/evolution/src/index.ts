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
 * Evolution Plugin for Agent-DH
 *
 * Strategy evolution and self-improvement via Agent OS.
 */
export default class EvolutionPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any)

  private aos: AgentOSClient;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'evolution');
    this.aos = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
      agentId: config.agentOS?.agentId || 'agent-dh',
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, aos } = this;

    // 进化运行
    ctx.tools.register(defineTool({
      name: 'evolution_run',
      description: '执行策略进化周期：回测参数变体、评估适应度、生成改进建议。用于：自动优化策略参数、发现更好的策略配置',
      parameters: {
        strategy_id: {
          type: 'integer',
          description: '策略ID，不传则对所有策略进行进化',
        },
        mode: {
          type: 'string',
          description: '进化模式：full（完整周期：生成建议+验证+回测）、propose（仅生成改进建议，默认）、validate（验证已有建议）',
          enum: ['full', 'propose', 'validate'],
          default: 'propose',
        },
        generations: {
          type: 'integer',
          description: '进化代数，默认3代',
          default: 3,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            strategy_id: { type: 'integer', description: '策略ID' },
            mode: { type: 'string', description: '进化模式' },
            proposals: { type: 'array', description: '改进建议列表' },
            best_params: { type: 'object', description: '最优参数', additionalProperties: true },
            fitness_improvement: { type: 'number', description: '适应度提升（%）' },
            backtest_result: { type: 'object', description: '回测结果', additionalProperties: true },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 60000,
      execute: async (args: any) => {
        return aos.evolution.run({
          strategy_id: args.strategy_id,
          mode: args.mode || 'propose',
          generations: args.generations || 3,
        }) as any;
      },
    } as any));

    // 进化排行榜
    ctx.tools.register(defineTool({
      name: 'evolution_leaderboard',
      description: '查询策略进化排行榜和适应度评分。用于：查看各策略的进化历史、比较不同策略的表现',
      parameters: {
        limit: {
          type: 'integer',
          description: '返回数量，默认10',
          default: 10,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            rankings: { type: 'array', description: '策略排名列表' },
            total_strategies: { type: 'integer', description: '策略总数' },
            avg_fitness: { type: 'number', description: '平均适应度' },
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
        return aos.evolution.getLeaderboard({
          limit: args.limit || 10,
        }) as any;
      },
    } as any));
  }
}
