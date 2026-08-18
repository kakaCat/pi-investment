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
      description: '执行策略进化：回测参数变体、评估适应度、生成改进建议（耗时操作，最长等待 60 秒）。适用于：定期（如每周）优化策略参数、策略表现下滑后寻找改进方向。查看各策略进化历史与排名用 evolution_leaderboard；验证改进后的策略用 strategy_execute(mode=backtest)。',
      parameters: {
        strategy_id: {
          type: 'integer',
          description: '策略ID。传入则只进化该策略；不传则对所有策略进化（耗时明显更长）',
        },
        mode: {
          type: 'string',
          description: '进化模式。propose（默认）：只生成改进建议，最快；validate：验证已有建议；full：完整周期（生成建议+验证+回测），最慢但结论最可靠',
          enum: ['full', 'propose', 'validate'],
          default: 'propose',
        },
        generations: {
          type: 'integer',
          description: '进化代数，默认 3。代数越多参数搜索越充分，耗时也越长',
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
      description: '查询策略进化排行榜：各策略的适应度评分与排名。适用于：比较策略优劣、决定启用/停用哪些策略、跟踪 evolution_run 的进化效果。',
      parameters: {
        limit: {
          type: 'integer',
          description: '返回排名数量，默认 10',
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
