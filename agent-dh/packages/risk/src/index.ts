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
 * Risk Management Plugin for Agent-DH
 *
 * Risk control, position sizing, portfolio risk assessment.
 */
export default class RiskPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'risk');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 风险控制
    ctx.tools.register(defineTool({
      name: 'risk_controller',
      description: '风险控制工具：计算建议仓位、止损位、评估组合风险。用于：买入前计算合理仓位、设置止损、检查组合风险是否超标',
      parameters: {
        command: {
          type: 'string',
          description: '操作类型：position_size（计算建议仓位）、stop_loss（计算止损价格）、portfolio_risk（评估组合整体风险）',
          enum: ['position_size', 'stop_loss', 'portfolio_risk'],
          required: true,
        },
        symbol: {
          type: 'string',
          description: '股票代码（position_size/stop_loss 时需要），如：600519',
        },
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            command: { type: 'string', description: '执行的操作' },
            symbol: { type: 'string', description: '股票代码' },
            result: { type: 'object', description: '计算结果', additionalProperties: true },
            warning: { type: 'string', description: '风险提示' },
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
        return qv2.riskControl({
          command: args.command,
          symbol: args.symbol,
          account_name: args.account_name || 'agent_virtual',
        }) as any;
      },
    } as any));

    // 风险指标
    ctx.tools.register(defineTool({
      name: 'risk_metrics',
      description: '计算投资组合风险指标。用于：评估组合波动率、最大回撤、夏普比率、Beta等风险指标',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
        days: {
          type: 'integer',
          description: '计算周期（天），默认60天',
          default: 60,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            volatility: { type: 'number', description: '年化波动率（%）' },
            max_drawdown: { type: 'number', description: '最大回撤（%）' },
            sharpe_ratio: { type: 'number', description: '夏普比率' },
            beta: { type: 'number', description: 'Beta系数（相对大盘）' },
            alpha: { type: 'number', description: 'Alpha超额收益（%）' },
            var_95: { type: 'number', description: 'VaR 95%（最大日亏损）' },
            sortino_ratio: { type: 'number', description: '索提诺比率' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        return qv2.getRiskMetrics({
          account_name: args.account_name || 'agent_virtual',
          days: args.days || 60,
        }) as any;
      },
    } as any));

    // Barra风险分解
    ctx.tools.register(defineTool({
      name: 'risk_barra_decomposition',
      description: '使用Barra模型分解组合风险来源。用于：识别风险来自哪些因子（市值、行业、风格等），指导风险调整',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            total_risk: { type: 'number', description: '总风险（%）' },
            factor_risks: { type: 'array', description: '各因子风险贡献' },
            idiosyncratic_risk: { type: 'number', description: '特质风险（%）' },
            industry_concentration: { type: 'number', description: '行业集中度' },
            style_exposure: { type: 'object', description: '风格暴露', additionalProperties: true },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 20000,
      execute: async (args: any) => {
        return qv2.getBarraDecomposition({
          account_name: args.account_name || 'agent_virtual',
        }) as any;
      },
    } as any));
  }
}
