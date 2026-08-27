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
  private osMemory: OsMemoryStore;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'intelligence');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.osMemory = new OsMemoryStore({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
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
          description: '触发条件表达式，create 时必填。支持：price>100（突破价格）、price<90（跌破价格）、change_pct>5（涨幅超5%）、change_pct<-3（跌幅超3%）',
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
        // 入参校验（2026-08-27：此前缺字段直达后端才报 400，错误信息晦涩）
        const { action, rule_id, name, symbol, condition } = args || {};
        if (action === 'create') {
          const missing = [];
          if (!name) missing.push('name（规则名称）');
          if (!symbol) missing.push('symbol（股票代码）');
          if (!condition) missing.push('condition（触发条件）');
          if (missing.length > 0) {
            throw new Error(`watch_manage create 缺少必填参数: ${missing.join('、')}。示例: action=create, name="茅台突破2000", symbol="600519", condition="price>2000"`);
          }
        } else if (['enable', 'disable', 'delete'].includes(action)) {
          if (!rule_id) {
            throw new Error(`watch_manage ${action} 缺少必填参数: rule_id。先用 watch_list 查询规则 ID`);
          }
        }
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

    // 4. 信号质量追踪（M3-1，2026-08-27 更新为调用 quantsys-v2 API）
    ctx.tools.register(defineTool({
      name: 'signal_track',
      description: '信号质量追踪（M3-1）：record 记录买入信号（标的/价格/来源/分级），update 回填 5/10/20 日表现（盘后例程调用），report 统计胜率。用于：评估信号质量、选择优胜策略、验证门裁决。',
      parameters: {
        action: {
          type: 'string',
          description: 'record=记录信号, update=回填表现, report=统计胜率',
          enum: ['record', 'update', 'report'],
          required: true,
        },
        symbol: {
          type: 'string',
          description: '股票代码（record 时必填）',
        },
        signal_date: {
          type: 'string',
          description: '信号日期 YYYY-MM-DD（record 时选填，默认今天）',
        },
        price: {
          type: 'number',
          description: '买入价格（record 时必填）',
        },
        source: {
          type: 'string',
          description: '信号来源（record 时必填）：strategy_execute / opportunity_scan / mainline_stocks / watch_rule',
        },
        grade: {
          type: 'string',
          description: '信号分级（record 时必填）：A=≥3维共振标准仓, B=2维或轻微矛盾半仓, C=单维只观察（参见 docs/architecture/signal-grading.md）',
          enum: ['A', 'B', 'C'],
        },
        reason: {
          type: 'string',
          description: '信号理由（record 时选填）',
        },
        lookback_days: {
          type: 'number',
          description: '回溯天数（update 时选填，默认30）',
        },
        start_date: {
          type: 'string',
          description: '开始日期（report 时选填）',
        },
        end_date: {
          type: 'string',
          description: '结束日期（report 时选填）',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            action: { type: 'string', description: '执行的动作' },
            result: { type: 'string', description: '结果摘要' },
            details: {
              type: 'object',
              description: '详细数据',
              additionalProperties: true,
            },
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
        const qv2 = this.qv2;

        if (args.action === 'record') {
          // 记录买入信号
          if (!args.symbol || !args.price || !args.source || !args.grade) {
            throw new Error('record 需要参数：symbol, price, source, grade');
          }

          const signal_date = args.signal_date || new Date().toISOString().slice(0, 10);

          const result = await qv2.recordSignal({
            signal_date,
            symbol: args.symbol,
            price: args.price,
            source: args.source,
            grade: args.grade as 'A' | 'B' | 'C',
            reason: args.reason,
          });

          return {
            action: 'record',
            result: `已记录信号 ID ${result.signalId}: ${args.symbol} (${args.grade}级)`,
            details: result,
          } as any;
        }

        if (args.action === 'update') {
          // 盘后回填表现
          const result = await qv2.updateSignalPerformance({
            signal_date: args.signal_date,
            lookback_days: args.lookback_days || 30,
          });

          return {
            action: 'update',
            result: `已更新 ${result.updated} 个信号的表现数据`,
            details: result,
          } as any;
        }

        if (args.action === 'report') {
          // 统计报告
          const result = await qv2.getSignalReport({
            start_date: args.start_date,
            end_date: args.end_date,
            grade: args.grade as 'A' | 'B' | 'C' | undefined,
            source: args.source,
          });

          // 生成摘要
          const gradeStats = Object.entries(result.byGrade || {})
            .filter(([_, v]: any) => v.count > 0)
            .map(([grade, stats]: any) => 
              `${grade}级: ${stats.count}个, 5日胜率${stats.hitRate5D ? (stats.hitRate5D * 100).toFixed(1) : 'N/A'}%`
            )
            .join(', ');

          return {
            action: 'report',
            result: `统计 ${result.total} 个信号 (${result.dateRange.start} ~ ${result.dateRange.end})。${gradeStats || '无数据'}`,
            details: result,
          } as any;
        }

        throw new Error(`未知 action: ${args.action}`);
      },
    } as any));
  }
}
