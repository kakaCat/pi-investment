import type { ToolPrompt } from '@pi-investment/core-tool';

export interface EvaluationReportParams {
  account_name?: string;
  start_date?: string;
  end_date?: string;
  annual_cost_rate?: number;
  include_ledger?: boolean;
}

function num(value: any, digits = 2): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'N/A';
}

export function renderEvaluationReport(value: any): string {
  const economy = value.accountEconomy || {};
  const ability = value.investmentAbility || {};
  const trade = value.tradeEconomy || {};
  const signal = value.signalEvaluation || {};
  const coverage = value.decisionCoverage || {};
  const winRate = typeof ability.winRate === 'number' ? `${num(ability.winRate * 100)}%` : 'N/A';
  const lines = [
    `## 投资评价报告｜${value.accountName || 'N/A'}`,
    `- 口径：只读；净值截至 ${economy.navAsOf || 'N/A'}；报告区间 ${value.period?.startDate || '全部历史'} → ${value.period?.endDate || 'N/A'}`,
    `- **账户经济账**：TWR ${num(economy.timeWeightedReturnPct)}%；外部净流入 ${num(economy.externalNetFlow)} 元；资金成本 ${num(economy.fundingCostToNavDate)} 元；扣成本经济损益 ${num(economy.economicPnlAfterFundingCost)} 元`,
    `- **投资能力账**：${ability.count ?? 0} 个关闭持仓回合；胜率 ${winRate}；平均每回合期望 ${num(ability.expectancy)} 元；样本状态 ${ability.sampleStatus || 'N/A'}`,
    `- **工程测试归因**：实现盈亏 ${num(trade.engineeringRealizedPnl)} 元（仍计入账户经济账，不进入投资能力账）`,
    `- **信号账**：${signal.scope || 'N/A'}；原始 ${signal.totalRecords ?? 0} 条，估算独立分组 ${signal.estimatedIndependentEpisodes ?? 0} 个；不可冒充本账户业绩`,
    `- **决策评分覆盖**：账户决策 ${coverage.decisionCount ?? 0} 条，已评分 ${coverage.scoredCount ?? 0} 条`,
  ];
  const warnings = value.dataQuality?.warnings || [];
  if (warnings.length) lines.push(`- **数据质量**：${warnings.join('；')}`);
  return lines.join('\n');
}

export const evaluationReportPrompt: ToolPrompt<EvaluationReportParams> = {
  description: '投资评价与业绩归因报告（只读）：严格分开账户经济账、投资能力账和全局未归属信号账；计算外部流调整TWR、资金成本、持仓回合胜率/平均盈亏/期望值，并公开工程测试排除清单。用于复盘真实亏损来源、判断策略是否有正期望。账户缺省取本实例投资账户配置，不写库、不改策略、不触发交易。',
  parameters: {
    account_name: { type: 'string', description: '模拟账户名；缺省取本实例投资账户配置，不得用其他账户样本替代' },
    start_date: { type: 'string', description: '报告开始日 YYYY-MM-DD；缺省取全部可得历史' },
    end_date: { type: 'string', description: '报告截止日 YYYY-MM-DD；缺省今天' },
    annual_cost_rate: { type: 'number', description: '年化资金成本率，0.02 表示 2%，默认 0.02' },
    include_ledger: { type: 'boolean', description: '是否附逐笔成交审计；默认 false，回合与排除清单仍保留' },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        schemaVersion: { type: 'string', description: '评价契约版本' },
        generatedAt: { type: 'string', description: '报告生成时点' },
        accountName: { type: 'string', description: '评价账户' },
        period: { type: 'object', additionalProperties: true, description: '报告区间' },
        accountCurrent: { type: 'object', additionalProperties: true, description: '当前账户与持仓' },
        accountEconomy: { type: 'object', additionalProperties: true, description: 'TWR、外部流、资金成本与扣成本经济损益' },
        tradeEconomy: { type: 'object', additionalProperties: true, description: '全部成交经济结果' },
        investmentAbility: { type: 'object', additionalProperties: true, description: '关闭回合样本、胜率、平均盈亏与期望值' },
        episodeSummary: { type: 'object', additionalProperties: true, description: '全部回合与投资回合汇总' },
        tradeEpisodes: { type: 'array', description: '持仓回合明细', items: { type: 'object', additionalProperties: true } },
        tradeLedger: { type: 'array', description: '逐笔成交审计，仅 include_ledger=true 返回', items: { type: 'object', additionalProperties: true } },
        signalEvaluation: { type: 'object', additionalProperties: true, description: '全局未归属信号统计，不是账户业绩' },
        decisionCoverage: { type: 'object', additionalProperties: true, description: '账户决策与评分覆盖' },
        dataQuality: { type: 'object', additionalProperties: true, description: '警告、排除与关联覆盖' },
      },
    },
    render: (_args: EvaluationReportParams, value: any) => [{ type: 'text', text: renderEvaluationReport(value) }],
  },
  examples: [
    { title: '复盘真实经济损益', params: { annual_cost_rate: 0.02 }, expectedResult: '返回剔除出入金后的TWR、2%资金成本和投资能力回合统计' },
    { title: '核对工程测试污染', params: { include_ledger: true }, expectedResult: '返回逐笔成交与显式工程测试排除依据' },
  ],
  useCases: [
    '回答账户实际赚亏、资金成本和策略期望值，而不是只看胜率',
    '将工程测试亏损从能力评价剔除，同时保留在账户经济账',
    '检查本账户决策评分覆盖是否足够支撑策略结论',
  ],
  notes: [
    'signal_tracking 无账户字段，全局信号统计不得冒充本账户业绩',
    '加仓和部分平仓合并为一个持仓回合；无样本返回 null/insufficient_sample',
  ],
  relatedTools: ['decision_scores：20交易日相对基准决策评分', 'risk_metrics：组合风险指标', 'trade_verify：当日成交对账'],
};
