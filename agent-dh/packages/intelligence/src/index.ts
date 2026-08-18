import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Intelligence Plugin for Agent-DH
 *
 * Market monitoring and alerting tools.
 */
export default class IntelligencePlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'intelligence');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 盯盘规则列表
    ctx.tools.register(defineTool({
      name: 'watch_list',
      description: '获取全部盯盘规则：监控标的、触发条件、启用状态、历史触发次数。盯盘规则在条件触发时会自动推送通知，无需人工盯盘。适用于：查看已有监控覆盖面、管理规则前确认 rule_id。创建/启停/删除规则用 watch_manage。',
      parameters: {},
      output: {
        schema: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'integer', description: '规则ID' },
              name: { type: 'string', description: '规则名称' },
              symbol: { type: 'string', description: '监控的股票代码' },
              condition: { type: 'string', description: '触发条件，如 price>100、change_pct>5' },
              enabled: { type: 'boolean', description: '是否启用' },
              created_at: { type: 'string', description: '创建时间' },
              updated_at: { type: 'string', description: '更新时间' },
              triggered_count: { type: 'integer', description: '历史触发次数' },
            },
            additionalProperties: true,
          },
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: `共找到 ${(value as any[]).length} 条盯盘规则:\n${JSON.stringify(value, null, 2)}`,
        }],
      },
      timeoutMs: 10000,
      execute: async () => {
        return qv2.listWatchRules() as any;
      },
    } as any));

    // 盯盘规则管理
    ctx.tools.register(defineTool({
      name: 'watch_manage',
      description: '管理盯盘规则（写操作）：创建、启用、禁用、删除。规则触发后系统自动通知，适合价格预警、涨跌幅预警、成交量异常监控等场景。创建前建议先用 watch_list 确认无重复规则。',
      parameters: {
        action: {
          type: 'string',
          description: '操作类型。create：创建新规则（需同时传 name、symbol、condition）；enable / disable / delete：对已有规则操作（需传 rule_id）',
          enum: ['create', 'enable', 'disable', 'delete'],
          required: true,
        },
        rule_id: {
          type: 'integer',
          description: '规则ID，enable/disable/delete 时必填，通过 watch_list 获取',
        },
        name: {
          type: 'string',
          description: '规则名称，create 时必填，如 "茅台价格突破2000"',
        },
        symbol: {
          type: 'string',
          description: '监控的股票代码，create 时必填，如 600519',
        },
        condition: {
          type: 'string',
          description: '触发条件表达式，create 时必填。支持：price>100（价格突破）、change_pct>5（涨幅超5%）、volume>1000000（成交量超100万股）',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean', description: '是否成功' },
            rule_id: { type: 'integer', description: '规则ID' },
            action: { type: 'string', description: '执行的操作' },
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
        return qv2.manageWatchRule(args) as any;
      },
    } as any));

    // 市场告警
    ctx.tools.register(defineTool({
      name: 'market_alert',
      description: '获取系统生成的市场告警：异常波动、重大事件、风险信号，按触发时间倒序返回。适用于：盘前/盘中定期查看市场异常动态。告警是系统主动发现的风险线索，high 级别应优先处理并评估是否影响持仓。',
      parameters: {
        level: {
          type: 'string',
          description: '告警级别过滤。all（默认）：全部；high：高风险，建议优先处理；medium：中等；low：低风险',
          enum: ['all', 'high', 'medium', 'low'],
          default: 'all',
        },
        limit: {
          type: 'integer',
          description: '返回数量上限，默认 20',
          default: 20,
        },
      },
      output: {
        schema: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'string', description: '告警ID' },
              level: { type: 'string', description: '级别：high/medium/low' },
              title: { type: 'string', description: '告警标题' },
              description: { type: 'string', description: '详细描述' },
              symbol: { type: 'string', description: '相关股票代码' },
              triggered_at: { type: 'string', description: '触发时间' },
            },
            additionalProperties: true,
          },
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: `共 ${(value as any[]).length} 条告警:\n${JSON.stringify(value, null, 2)}`,
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return qv2.getAlerts({
          level: args.level || 'all',
          limit: args.limit || 20,
        }) as any;
      },
    } as any));
  }
}
