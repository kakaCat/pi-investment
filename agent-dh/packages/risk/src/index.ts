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
      description: '风险控制计算：建议仓位、止损价、组合风险评估。适用于：买入前用 position_size 计算合理仓位、开仓后用 stop_loss 设置止损、定期用 portfolio_risk 检查组合风险是否超标。只读计算，不改变持仓；执行交易用 portfolio_trade。',
      parameters: {
        command: {
          type: 'string',
          description: '操作类型。position_size：根据账户资金与标的风险计算建议买入仓位（需传 symbol）；stop_loss：计算止损价格（需传 symbol）；portfolio_risk：评估组合整体风险是否超标',
          enum: ['position_size', 'stop_loss', 'portfolio_risk'],
          required: true,
        },
        symbol: {
          type: 'string',
          description: '股票代码，position_size / stop_loss 时必填，如 600519',
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
        render: (_args: any, value: any) => [{
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
      description: '计算投资组合的风险收益指标：年化波动率、最大回撤、夏普/索提诺比率、Beta、Alpha、VaR(95%)。适用于：定期（如每周）评估组合风险收益特征、判断是否需要降仓。需要因子层面的风险来源分解时用 risk_barra_decomposition。',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
        days: {
          type: 'integer',
          description: '计算窗口（天），默认 60。窗口越短对近期变化越敏感，越长越稳定',
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
        render: (_args: any, value: any) => [{
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
      description: '用 Barra 模型将组合风险分解到因子层面（市值、行业、风格），给出各因子风险贡献与特质风险。适用于：组合回撤异常时定位风险来源、检查行业/风格暴露是否过度集中。整体风险指标用 risk_metrics。',
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
        render: (_args: any, value: any) => [{
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

    // M4 仓位映射表（RFC 004，2026-08-21）：regime → 权益仓位上限，含回撤熔断检查
    ctx.tools.register(defineTool({
      name: 'regime_position_limit',
      description: 'M4 仓位映射：读取最新落库的 regime（market:regime），返回权益仓位上限（恐慌≤100%/偏多≤80%/震荡≤60%/偏空≤40%/狂热≤30%）、当前实际仓位、余量与合规判定（可加仓/须减仓及额度）；同时检查组合回撤熔断（60日最大回撤超8%触发，要求减仓一半）。数据降级（degraded/指标矛盾）时上限自动收紧到震荡档（保守原则）。买入前必须调用（R-001 配套）。',
      parameters: {
        account_name: { type: 'string', description: '账户名称，默认 agent_virtual', default: 'agent_virtual' },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            regime: { type: 'string' },
            regime_date: { type: 'string' },
            data_quality: { type: 'string' },
            max_position_pct: { type: 'number', description: 'regime 映射的权益仓位上限（%）' },
            current_position_pct: { type: 'number' },
            headroom_pct: { type: 'number', description: '剩余可加仓空间（%），负数=超限' },
            verdict: { type: 'string', description: 'compliant / reduce_required / circuit_breaker' },
            circuit_breaker: { type: 'object', additionalProperties: true },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 20000,
      execute: async (args: any) => {
        // 1. 读最新 regime 记录（忽略已弃用）
        const res = await qv2.searchMemory({ q: 'regime', scope: 'market:regime', limit: 10 });
        const latest = (res?.items || [])
          .filter((it: any) => it.status !== 'deprecated' && it.payload?.date)
          .sort((a: any, b: any) => String(b.payload.date).localeCompare(String(a.payload.date)))[0];

        const regime = latest?.payload?.regime ?? 'sideways';
        const dataQuality = latest?.payload?.evidence?.data_quality ?? 'unknown';
        const conflicts = latest?.payload?.evidence?.conflicts ?? null;

        // 2. 映射表（RFC 004 M4-1）；数据降级时收紧到震荡档（保守原则）
        const CAPS: Record<string, number> = { panic: 100, risk_on: 80, sideways: 60, risk_off: 40, euphoria: 30 };
        const rawCap = CAPS[regime] ?? 60;
        let cap = rawCap;
        let capNote = '';
        if (dataQuality === 'degraded' || (Array.isArray(conflicts) && conflicts.length > 0)) {
          cap = Math.min(cap, 60);
          // 只有实际收紧了才提示（如 euphoria 本身 30% 已低于震荡档，不算收紧）
          if (cap < rawCap) {
            capNote = `数据降级/指标矛盾，上限由 ${rawCap}% 收紧至 ${cap}%（保守）`;
          }
        }

        // 3. 当前仓位
        const summary: any = await qv2.getPortfolioSummary(args.account_name || 'agent_virtual');
        const totalValue = Number(summary?.totalValue ?? 0);
        const marketValue = Number(summary?.totalMarketValue ?? 0);
        const currentPct = totalValue > 0 ? +(marketValue / totalValue * 100).toFixed(1) : 0;
        const headroom = +(cap - currentPct).toFixed(1);

        // 4. 回撤熔断（60 日最大回撤超 8% → 减仓一半）
        // 2026-08-21 E2E 修正：后端真实字段是 maxDrawdown（camelCase）且为小数比率
        // （-0.0716 = -7.16%），不是 max_drawdown 百分数——E2E 前读的是错的
        let circuit: any = { triggered: false };
        let verdict = headroom >= 0 ? 'compliant' : 'reduce_required';
        try {
          const metrics: any = await qv2.getRiskMetrics({ account_name: args.account_name || 'agent_virtual', days: 60 });
          const raw = Number(metrics?.maxDrawdown ?? metrics?.max_drawdown ?? 0);
          const mdd = Math.abs(raw) <= 1 ? +(raw * 100).toFixed(2) : raw;  // 小数比率→百分比
          if (mdd <= -8) {
            circuit = {
              triggered: true,
              max_drawdown: mdd,
              action: '组合回撤熔断触发：强制减仓一半（权益仓位降至当前 50%），禁止新开仓直到回撤修复',
            };
            verdict = 'circuit_breaker';
          } else {
            circuit = { triggered: false, max_drawdown: mdd, threshold: -8 };
          }
        } catch {
          circuit = { triggered: false, note: '回撤指标不可用，熔断未评估' };
        }

        return {
          regime,
          regime_date: latest?.payload?.date ?? null,
          data_quality: dataQuality,
          max_position_pct: cap,
          current_position_pct: currentPct,
          headroom_pct: headroom,
          verdict,
          cap_note: capNote || null,
          reduce_to_pct: verdict === 'reduce_required' ? cap : null,
          circuit_breaker: circuit,
          mapping_table: CAPS,
        } as any;
      },
    } as any));
  }
}
