import { BaseTool, ToolResponse, ValidationResult, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { factorCalculatePrompt, type FactorCalculateParams, type FactorCalculateResult } from './prompt';

/**
 * 资金类因子名单（2026-09-11，REQ-cf627b）
 *
 * 实测（600150，2026-09-11 02:5x，GET /api/stock/600150/factors）：
 * 下列 10 个资金因子在后端因子表中全部为 0.0，且 factor_date=2026-09-10 / stale=False
 * —— 即「新鲜的假数据」；而 provider /api/stock/600150/fund-flow 同标的 2026-09-09
 * 主力净流入 68372.88 万。两处互相矛盾，工具层此前无护栏，会导致 R-009 的
 * 「资金面共振」维度恒为 0（看似有值，实为静默失效）。
 */
const FUND_FACTORS = [
  'super_large_net', 'large_net', 'main_net_pct', 'super_large_pct', 'large_pct',
  'fund_inflow_pos_days_5', 'fund_inflow_pos_days_3', 'fund_inflow_3d_sum',
  'fund_inflow_5d_sum', 'main_net_inflow',
] as const;

export class FactorCalculateTool extends BaseTool<FactorCalculateParams, FactorCalculateResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'factor_calculate',
    category: 'factor',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = factorCalculatePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(params: FactorCalculateParams): ValidationResult {
    const { symbol, factors } = params;

    // 检查 symbol 格式
    if (!symbol || !/^\d{6}$/.test(symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: `无效的股票代码格式: ${symbol}`,
        expected: 'A股6位数字代码，如 600519',
      };
    }

    // 检查 factors 数组（如果提供）
    const validFactors = ['rsi', 'macd', 'pe', 'pb', 'roe', 'turnover', 'volatility'];
    if (factors && factors.length > 0) {
      const invalidFactors = factors.filter(f => !validFactors.includes(f));
      if (invalidFactors.length > 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'factors',
          issue: `无效的因子: ${invalidFactors.join(', ')}`,
          expected: validFactors.join(', '),
        };
      }
    }

    return { success: true };
  }

  protected async execute(params: FactorCalculateParams, context: ToolContext): Promise<FactorCalculateResult> {
    const { symbol, factors } = params;

    const raw: any = await this.qv2.calculateFactors({
      symbol,
      factors,
    });

    // 后端实际返回 factors 为数组 [{factor_name, factor_value, factor_date, symbol}]，
    // 与输出契约的「因子值字典」不符。在边界处归一化：同名因子取最新日期的值，
    // 并附带 factor_dates 便于识别陈旧数据（如技术指标滞后数月）。
    if (Array.isArray(raw?.factors)) {
      const dict: Record<string, unknown> = {};
      const dates: Record<string, string> = {};
      for (const f of raw.factors) {
        const name = f?.factor_name;
        if (!name) continue;
        const date = String(f?.factor_date ?? '');
        if (!(name in dates) || date > dates[name]) {
          dates[name] = date;
          dict[name] = f?.factor_value;
        }
      }

      // 2026-08-28 根本性修复：因子数据 freshness 校验，防止静默毒化选股质量
      const now = new Date();
      const warnings: string[] = [];
      const errors: string[] = [];
      for (const [name, dateStr] of Object.entries(dates)) {
        if (!dateStr) continue;
        const factorDate = new Date(dateStr);
        const staleDays = Math.floor((now.getTime() - factorDate.getTime()) / 86400000);
        if (staleDays > 7) {
          errors.push(`${name} 数据过期 ${staleDays} 天（${dateStr}），超过 7 天阈值`);
        } else if (staleDays > 3) {
          warnings.push(`${name} 数据陈旧 ${staleDays} 天（${dateStr}）`);
        }
      }

      if (errors.length > 0) {
        throw new Error(`因子数据过期拒绝服务：${errors.join('; ')}。请触发因子计算管道补录或联系后端排查。`);
      }

      // 2026-09-11 护栏（REQ-cf627b）：资金类因子「静默全 0」检测 + 与 provider 资金流对账。
      // 规则：资金因子全 0 时不信任该组数据 —— 剔除 + degraded + 附 provider 真实资金面快照，
      // 让调用方拿不到「看起来有效的 0」，而不是把 0 当结论用（R-013：禁止不可溯源数据入决策）。
      const presentFunds = FUND_FACTORS.filter((n) => n in dict);
      const allFundZero = presentFunds.length > 0 && presentFunds.every((n) => Number(dict[n]) === 0);
      let unavailableFunds: string[] = [];
      let fundProvider: Record<string, unknown> | undefined;
      if (allFundZero) {
        let providerMain: number | null = null;
        let providerDate: string | null = null;
        try {
          const pf: any = await (this.qv2 as any).getStockFundFlow(symbol, 5);
          const rows: any = pf?.data?.data ?? pf?.data ?? [];
          const row = Array.isArray(rows)
            ? rows.find((r: any) => r?.mainNetInflow !== undefined && r?.mainNetInflow !== null)
            : null;
          if (row) {
            providerMain = Number(row.mainNetInflow);
            providerDate = String(row.date ?? '');
          }
        } catch {
          // provider 不可用时按「无法确认」处理，不因此放行 0 值
        }
        const contradictory = providerMain !== null && Math.abs(providerMain) > 0;
        unavailableFunds = [...presentFunds];
        for (const n of presentFunds) delete dict[n];
        if (contradictory) {
          warnings.push(
            `资金类因子疑似静默失效：后端返回 ${presentFunds.length} 个资金因子全为 0，但 provider 资金流同标的 ${providerDate} 主力净流入 ${providerMain} 万 → 已剔除该组因子，禁止用于资金面共振判定；资金面请改用 fund_flow 工具。`,
          );
        } else {
          warnings.push(
            `资金类因子全为 0 且 provider 资金流亦为空/0：资金面无法确认，已剔除 ${presentFunds.length} 个资金因子；不得把 0 解读为「零资金流」。`,
          );
        }
        if (providerMain !== null) {
          fundProvider = {
            source: 'fund_flow provider (/api/stock/{symbol}/fund-flow)',
            date: providerDate,
            main_net_inflow_wan: providerMain,
            contradicts_factor_table: contradictory,
          };
        }
      }

      // 2026-08-30 修复：freshness_warnings: undefined 显式键会导致 lossless 校验失败，改条件展开
      return sanitizeLossless({
        ...raw,
        factors: dict,
        factor_dates: dates,
        ...(unavailableFunds.length > 0
          ? { unavailable_factors: unavailableFunds, ...(fundProvider ? { fund_flow_provider: fundProvider } : {}) }
          : {}),
        ...(warnings.length > 0 ? { freshness_warnings: warnings, degraded: true } : { degraded: false }),
      });
    }

    return raw;
  }

  protected wrap(data: FactorCalculateResult, _context: ToolContext): ToolResponse<FactorCalculateResult> {
    return {
      success: true,
      data,
    };
  }
}
