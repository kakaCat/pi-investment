/**
 * Data formatters for quantsys-v2 API responses
 * Converts JSON responses into human-readable text format for Agent consumption
 */

import type {
  FinancialData,
  FactorResult,
  OpportunityResult,
  AlgoOrderResult,
} from './types.js';

/**
 * Constant for converting to 亿元 (hundred millions)
 */
const YI = 100000000;

/**
 * Format a number with thousands separators
 */
export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return 'N/A';
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Format a percentage value
 */
export function formatPercent(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return 'N/A';
  const sign = value > 0 ? '+' : '';
  return `${sign}${formatNumber(value, decimals)}%`;
}

/**
 * Format financial data into readable text
 */
export function formatFinancialData(data: FinancialData): string {
  const lines: string[] = [];

  lines.push(`股票代码: ${data.symbol}`);
  lines.push(`股票名称: ${data.name}`);
  lines.push(`报告期: ${data.report_date}`);
  lines.push('');

  // Income statement
  if (data.income_statement) {
    const income = data.income_statement;
    lines.push('【利润表】');
    const revenue = income.revenue ?? 0;
    const operatingCost = income.operating_cost ?? 0;
    const grossProfit = income.gross_profit ?? 0;
    const netProfit = income.net_profit ?? 0;
    const netProfitAttrParent = income.net_profit_attr_parent ?? 0;
    lines.push(`  营业收入: ${formatNumber(revenue / YI, 2)} 亿元`);
    lines.push(`  营业成本: ${formatNumber(operatingCost / YI, 2)} 亿元`);
    lines.push(`  毛利润: ${formatNumber(grossProfit / YI, 2)} 亿元`);
    lines.push(`  净利润: ${formatNumber(netProfit / YI, 2)} 亿元`);
    lines.push(`  归母净利润: ${formatNumber(netProfitAttrParent / YI, 2)} 亿元`);
    lines.push(`  毛利率: ${formatPercent(income.gross_margin)}`);
    lines.push(`  净利率: ${formatPercent(income.net_margin)}`);
    lines.push('');
  }

  // Balance sheet
  if (data.balance_sheet) {
    const balance = data.balance_sheet;
    lines.push('【资产负债表】');
    const totalAssets = balance.total_assets ?? 0;
    const currentAssets = balance.current_assets ?? 0;
    const totalLiabilities = balance.total_liabilities ?? 0;
    const currentLiabilities = balance.current_liabilities ?? 0;
    const totalEquity = balance.total_equity ?? 0;
    lines.push(`  总资产: ${formatNumber(totalAssets / YI, 2)} 亿元`);
    lines.push(`  流动资产: ${formatNumber(currentAssets / YI, 2)} 亿元`);
    lines.push(`  总负债: ${formatNumber(totalLiabilities / YI, 2)} 亿元`);
    lines.push(`  流动负债: ${formatNumber(currentLiabilities / YI, 2)} 亿元`);
    lines.push(`  股东权益: ${formatNumber(totalEquity / YI, 2)} 亿元`);
    lines.push(`  资产负债率: ${formatPercent(balance.debt_ratio)}`);
    lines.push(`  流动比率: ${formatNumber(balance.current_ratio, 2)}`);
    lines.push('');
  }

  // Cash flow statement
  if (data.cash_flow) {
    const cashflow = data.cash_flow;
    lines.push('【现金流量表】');
    const operatingCashflow = cashflow.operating_cashflow ?? 0;
    const investingCashflow = cashflow.investing_cashflow ?? 0;
    const financingCashflow = cashflow.financing_cashflow ?? 0;
    const netCashflow = cashflow.net_cashflow ?? 0;
    lines.push(`  经营活动现金流: ${formatNumber(operatingCashflow / YI, 2)} 亿元`);
    lines.push(`  投资活动现金流: ${formatNumber(investingCashflow / YI, 2)} 亿元`);
    lines.push(`  筹资活动现金流: ${formatNumber(financingCashflow / YI, 2)} 亿元`);
    lines.push(`  现金净增加额: ${formatNumber(netCashflow / YI, 2)} 亿元`);
    lines.push('');
  }

  // Key metrics
  if (data.metrics) {
    const metrics = data.metrics;
    lines.push('【关键指标】');
    lines.push(`  市盈率(PE): ${formatNumber(metrics.pe_ratio, 2)}`);
    lines.push(`  市净率(PB): ${formatNumber(metrics.pb_ratio, 2)}`);
    lines.push(`  净资产收益率(ROE): ${formatPercent(metrics.roe)}`);
    lines.push(`  总资产收益率(ROA): ${formatPercent(metrics.roa)}`);
    lines.push(`  每股收益(EPS): ${formatNumber(metrics.eps, 2)} 元`);
    lines.push(`  每股净资产(BVPS): ${formatNumber(metrics.bvps, 2)} 元`);
  }

  return lines.join('\n');
}

/**
 * Format factor calculation result into readable text
 */
export function formatFactorResult(result: FactorResult): string {
  const lines: string[] = [];

  if (!result.success || !result.results || result.results.length === 0) {
    return '因子计算失败或无结果';
  }

  // Process each symbol's result
  for (const item of result.results) {
    if (item.error) {
      lines.push(`股票代码: ${item.symbol}`);
      lines.push(`错误: ${item.error}`);
      lines.push('');
      continue;
    }

    lines.push(`股票代码: ${item.symbol}`);
    lines.push(`计算时间: ${item.date}`);
    lines.push(`因子数量: ${item.factor_count}`);
    lines.push('');

    const factors = item.factors;

    // Technical factors
    const technicalFactors: Record<string, string> = {};
    if (factors.rsi !== undefined && factors.rsi !== null) {
      technicalFactors['RSI(14)'] = formatNumber(factors.rsi, 2);
    }
    if (factors.macd !== undefined && factors.macd !== null) {
      technicalFactors['MACD'] = formatNumber(factors.macd, 4);
    }
    if (factors.macd_signal !== undefined && factors.macd_signal !== null) {
      technicalFactors['MACD信号线'] = formatNumber(factors.macd_signal, 4);
    }
    if (factors.macd_hist !== undefined && factors.macd_hist !== null) {
      technicalFactors['MACD柱'] = formatNumber(factors.macd_hist, 4);
    }
    if (factors.kdj_k !== undefined && factors.kdj_k !== null) {
      technicalFactors['KDJ-K'] = formatNumber(factors.kdj_k, 2);
    }
    if (factors.kdj_d !== undefined && factors.kdj_d !== null) {
      technicalFactors['KDJ-D'] = formatNumber(factors.kdj_d, 2);
    }
    if (factors.kdj_j !== undefined && factors.kdj_j !== null) {
      technicalFactors['KDJ-J'] = formatNumber(factors.kdj_j, 2);
    }
    if (factors.boll_upper !== undefined && factors.boll_upper !== null) {
      technicalFactors['布林上轨'] = formatNumber(factors.boll_upper, 2);
    }
    if (factors.boll_mid !== undefined && factors.boll_mid !== null) {
      technicalFactors['布林中轨'] = formatNumber(factors.boll_mid, 2);
    }
    if (factors.boll_lower !== undefined && factors.boll_lower !== null) {
      technicalFactors['布林下轨'] = formatNumber(factors.boll_lower, 2);
    }

    if (Object.keys(technicalFactors).length > 0) {
      lines.push('【技术因子】');
      for (const [name, value] of Object.entries(technicalFactors)) {
        lines.push(`  ${name}: ${value}`);
      }
      lines.push('');
    }

    // Fundamental factors
    const fundamentalFactors: Record<string, string> = {};
    if (factors.pe_ratio !== undefined && factors.pe_ratio !== null) {
      fundamentalFactors['市盈率(PE)'] = formatNumber(factors.pe_ratio, 2);
    }
    if (factors.pb_ratio !== undefined && factors.pb_ratio !== null) {
      fundamentalFactors['市净率(PB)'] = formatNumber(factors.pb_ratio, 2);
    }
    if (factors.roe !== undefined && factors.roe !== null) {
      fundamentalFactors['净资产收益率(ROE)'] = formatPercent(factors.roe);
    }
    if (factors.roa !== undefined && factors.roa !== null) {
      fundamentalFactors['总资产收益率(ROA)'] = formatPercent(factors.roa);
    }
    if (factors.gross_margin !== undefined && factors.gross_margin !== null) {
      fundamentalFactors['毛利率'] = formatPercent(factors.gross_margin);
    }
    if (factors.net_margin !== undefined && factors.net_margin !== null) {
      fundamentalFactors['净利率'] = formatPercent(factors.net_margin);
    }
    if (factors.debt_ratio !== undefined && factors.debt_ratio !== null) {
      fundamentalFactors['资产负债率'] = formatPercent(factors.debt_ratio);
    }

    if (Object.keys(fundamentalFactors).length > 0) {
      lines.push('【基本面因子】');
      for (const [name, value] of Object.entries(fundamentalFactors)) {
        lines.push(`  ${name}: ${value}`);
      }
      lines.push('');
    }

    // Composite score if available
    if (factors.composite_score !== undefined && factors.composite_score !== null) {
      lines.push('【综合评分】');
      lines.push(`  综合得分: ${formatNumber(factors.composite_score, 2)}/100`);

      if (factors.composite_score >= 80) {
        lines.push(`  评级: 优秀 ⭐⭐⭐⭐⭐`);
      } else if (factors.composite_score >= 60) {
        lines.push(`  评级: 良好 ⭐⭐⭐⭐`);
      } else if (factors.composite_score >= 40) {
        lines.push(`  评级: 中等 ⭐⭐⭐`);
      } else {
        lines.push(`  评级: 较差 ⭐⭐`);
      }
      lines.push('');
    }
  }

  return lines.join('\n');
}

/**
 * Format opportunity scan results into readable text
 */
export function formatOpportunities(opportunities: OpportunityResult[]): string {
  if (opportunities.length === 0) {
    return '未发现符合条件的投资机会';
  }

  const lines: string[] = [];
  lines.push(`发现 ${opportunities.length} 个投资机会:\n`);

  opportunities.forEach((opp, index) => {
    lines.push(`${index + 1}. ${opp.name} (${opp.symbol})`);
    lines.push(`   综合得分: ${formatNumber(opp.score, 2)}/100`);
    lines.push(`   技术得分: ${formatNumber(opp.technical_score, 2)}`);
    lines.push(`   基本面得分: ${formatNumber(opp.fundamental_score, 2)}`);
    lines.push(`   资金得分: ${formatNumber(opp.capital_score, 2)}`);
    lines.push(`   置信度: ${formatPercent(opp.confidence * 100, 1)}`);
    lines.push(`   风险等级: ${opp.risk_level}`);
    lines.push(`   信号类型: ${opp.signal_type}`);

    if (opp.reasons && opp.reasons.length > 0) {
      lines.push(`   推荐理由:`);
      opp.reasons.forEach(reason => {
        lines.push(`     - ${reason}`);
      });
    }

    lines.push(`   扫描时间: ${opp.timestamp}`);
    lines.push('');
  });

  return lines.join('\n');
}

/**
 * Format algo order result into readable text
 */
export function formatAlgoOrder(order: AlgoOrderResult): string {
  const lines: string[] = [];

  lines.push(`算法订单ID: ${order.order_id}`);
  lines.push(`股票代码: ${order.symbol}`);
  lines.push(`股票名称: ${order.name}`);
  lines.push(`订单方向: ${order.side === 'buy' ? '买入' : '卖出'}`);
  lines.push(`算法类型: ${order.algo_type}`);
  lines.push(`订单状态: ${order.status}`);
  lines.push('');

  lines.push('【订单参数】');
  lines.push(`  目标数量: ${formatNumber(order.target_quantity, 0)} 股`);
  lines.push(`  已成交数量: ${formatNumber(order.filled_quantity, 0)} 股`);
  lines.push(`  剩余数量: ${formatNumber(order.remaining_quantity, 0)} 股`);
  const progress = order.target_quantity > 0
    ? (order.filled_quantity / order.target_quantity) * 100
    : 0;
  lines.push(`  完成进度: ${formatPercent(progress, 1)}`);
  lines.push('');

  if (order.limit_price) {
    lines.push(`  限价: ${formatNumber(order.limit_price, 2)} 元`);
  }
  if (order.avg_price) {
    lines.push(`  平均成交价: ${formatNumber(order.avg_price, 2)} 元`);
  }
  lines.push('');

  lines.push('【时间信息】');
  lines.push(`  创建时间: ${order.created_at}`);
  lines.push(`  开始时间: ${order.start_time}`);
  lines.push(`  结束时间: ${order.end_time}`);
  if (order.updated_at) {
    lines.push(`  更新时间: ${order.updated_at}`);
  }
  if (order.completed_at) {
    lines.push(`  完成时间: ${order.completed_at}`);
  }
  lines.push('');

  // Algorithm-specific parameters
  if (order.algo_params) {
    lines.push('【算法参数】');
    const params = order.algo_params;

    if (params.participation_rate !== undefined) {
      lines.push(`  参与率: ${formatPercent(params.participation_rate * 100, 1)}`);
    }
    if (params.urgency !== undefined) {
      lines.push(`  紧急度: ${params.urgency}`);
    }
    if (params.price_limit !== undefined) {
      lines.push(`  价格限制: ${formatNumber(params.price_limit, 2)} 元`);
    }
    if (params.time_limit !== undefined) {
      lines.push(`  时间限制: ${params.time_limit} 秒`);
    }
    lines.push('');
  }

  // Execution statistics
  if (order.execution_stats) {
    lines.push('【执行统计】');
    const stats = order.execution_stats;

    if (stats.total_trades !== undefined) {
      lines.push(`  总成交笔数: ${stats.total_trades}`);
    }
    if (stats.avg_trade_size !== undefined) {
      lines.push(`  平均每笔数量: ${formatNumber(stats.avg_trade_size, 0)} 股`);
    }
    if (stats.total_commission !== undefined) {
      lines.push(`  总手续费: ${formatNumber(stats.total_commission, 2)} 元`);
    }
    if (stats.slippage !== undefined) {
      lines.push(`  滑点: ${formatNumber(stats.slippage, 4)} 元`);
    }
    if (stats.vwap !== undefined) {
      lines.push(`  VWAP: ${formatNumber(stats.vwap, 2)} 元`);
    }
    lines.push('');
  }

  // Error information
  if (order.error_message) {
    lines.push('【错误信息】');
    lines.push(`  ${order.error_message}`);
    lines.push('');
  }

  return lines.join('\n');
}

/**
 * Format factor analysis result into readable text
 */
export function formatFactorAnalysis(analysis: import('./types.js').FactorAnalysis): string {
  const lines: string[] = [];

  if (!analysis.success || !analysis.factors || analysis.factors.length === 0) {
    return '因子分析失败或无结果';
  }

  lines.push(`因子分析结果（共 ${analysis.factors.length} 个因子）:\n`);

  for (const factor of analysis.factors) {
    lines.push(`【${factor.name}】`);
    lines.push(`  日度IC: ${formatNumber(factor.ic_daily, 4)}`);
    lines.push(`  周度IC: ${formatNumber(factor.ic_weekly, 4)}`);
    lines.push(`  月度IC: ${formatNumber(factor.ic_monthly, 4)}`);
    lines.push(`  覆盖率: ${formatPercent(factor.coverage * 100, 2)}`);
    lines.push(`  稳定性: ${formatNumber(factor.stability, 4)}`);

    if (factor.decay_curve && factor.decay_curve.length > 0) {
      const decayStr = factor.decay_curve
        .slice(0, 10)  // Show first 10 periods
        .map(v => formatNumber(v, 3))
        .join(', ');
      lines.push(`  衰减曲线: [${decayStr}${factor.decay_curve.length > 10 ? ', ...' : ''}]`);
    }

    lines.push('');
  }

  return lines.join('\n');
}
