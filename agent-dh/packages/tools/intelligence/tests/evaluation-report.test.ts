import { describe, expect, it } from 'vitest';
import { EvaluationReportTool } from '../src/tools/EvaluationReportTool/EvaluationReportTool';
import { renderEvaluationReport } from '../src/tools/EvaluationReportTool/prompt';

function fixture() {
  return {
    schemaVersion: 'investment_evaluation_v1',
    generatedAt: '2026-11-02T10:00:00',
    readOnly: true,
    accountName: 'test_account',
    period: { startDate: null, endDate: '2026-11-02' },
    accountCurrent: {},
    accountEconomy: {
      navAsOf: '2026-10-30', timeWeightedReturnPct: -1.09,
      externalNetFlow: 401077.03, fundingCostToNavDate: 1636.29,
      economicPnlAfterFundingCost: -4364.76,
      intervals: [{ return: 0.01 }],
    },
    tradeEconomy: { engineeringRealizedPnl: -1394.95 },
    investmentAbility: { count: 2, winRate: 0, expectancy: -714.395, sampleStatus: 'small_sample' },
    episodeSummary: {}, tradeEpisodes: [], tradeLedger: [{ id: 1 }],
    signalEvaluation: { scope: 'global_unassigned', totalRecords: 188, estimatedIndependentEpisodes: 153 },
    decisionCoverage: { decisionCount: 255, scoredCount: 0 },
    dataQuality: { warnings: [] },
  };
}

describe('evaluation_report 工具', () => {
  it('显式传账户和资金成本，默认裁剪长区间与逐笔账本', async () => {
    const calls: any[] = [];
    const qv2 = {
      getInvestmentEvaluationReport: async (params: any) => { calls.push(params); return fixture(); },
    } as any;
    const tool = new EvaluationReportTool(qv2);
    const data = await (tool as any).execute({ account_name: 'test_account', annual_cost_rate: 0.02 }, {});
    expect(calls).toEqual([{
      account_name: 'test_account', start_date: undefined, end_date: undefined, annual_cost_rate: 0.02,
    }]);
    expect(data.accountEconomy.intervals).toBeUndefined();
    expect(data.tradeLedger).toBeUndefined();
    expect(data.tradeLedgerOmitted).toBe(true);
    expect(data.investmentAbility.count).toBe(2);
  });

  it('include_ledger=true 时保留逐笔审计', async () => {
    const qv2 = { getInvestmentEvaluationReport: async () => fixture() } as any;
    const tool = new EvaluationReportTool(qv2);
    const data = await (tool as any).execute({ include_ledger: true }, {});
    expect(data.tradeLedger).toEqual([{ id: 1 }]);
    expect(data.tradeLedgerOmitted).toBe(false);
  });

  it('拒绝非法日期和资金成本率', () => {
    const tool = new EvaluationReportTool({} as any);
    expect((tool as any).validate({ start_date: '2026/11/02' }).success).toBe(false);
    expect((tool as any).validate({ annual_cost_rate: 1.2 }).success).toBe(false);
    expect((tool as any).validate({ annual_cost_rate: 0.02 }).success).toBe(true);
  });

  it('渲染同时呈现经济账、能力账和信号归属限制', () => {
    const text = renderEvaluationReport(fixture());
    expect(text).toContain('-1.09%');
    expect(text).toContain('2 个关闭持仓回合');
    expect(text).toContain('胜率 0.00%');
    expect(text).toContain('不可冒充本账户业绩');
  });
});
