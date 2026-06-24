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
 * Format stock price data with real-time indicator
 */
export function formatStockPrice(data: any): string {
  if (!data) return '价格数据不可用';

  // ===== 数据验证：防止异常数据 =====
  const price = data.price ?? 0;
  const changePct = data.changePct ?? data.change_pct ?? 0;
  const prevClose = data.prevClose ?? data.prev_close ?? 0;

  // 验证价格范围（A股正常价格 0.01 - 10000 元）
  if (price > 100000 || price < 0) {
    return `❌ 数据异常：股票 ${data.symbol} 价格超出合理范围 (${price} 元)。请检查数据源。`;
  }

  // 验证涨跌幅范围（A股单日涨跌幅限制约 ±20%，ST股票 ±5%）
  if (Math.abs(changePct) > 30) {
    return `❌ 数据异常：股票 ${data.symbol} 涨跌幅超出合理范围 (${changePct.toFixed(2)}%)。请检查数据源。`;
  }

  // 验证昨收价格
  if (prevClose > 100000 || prevClose < 0) {
    return `❌ 数据异常：股票 ${data.symbol} 昨收价超出合理范围 (${prevClose} 元)。请检查数据源。`;
  }

  const lines: string[] = [];

  // Detect data source type
  const realtimeSources = ['akshare', 'sina', 'eastmoney', 'tencent', 'netease'];
  const isRealtime = data.source && realtimeSources.includes(data.source);
  const isFallback = data.source === 'db_fallback';

  // Source name mapping
  const sourceNames: Record<string, string> = {
    'sina': '新浪财经',
    'eastmoney': '东方财富',
    'tencent': '腾讯财经',
    'netease': '网易财经',
    'akshare': 'AKShare',
    'db_fallback': '数据库'
  };

  // Header with data source indicator
  if (isRealtime) {
    const sourceName = sourceNames[data.source] || data.source;
    lines.push(`【实时行情】（${sourceName}，延迟 < 3秒）`);
  } else if (isFallback) {
    lines.push('【最新收盘价】（数据库，非实时）');
  } else {
    lines.push('【行情数据】');
  }

  lines.push(`股票代码: ${data.symbol}`);
  lines.push(`股票名称: ${data.name}`);
  lines.push(`当前价格: ${formatNumber(price, 2)} 元`);

  // Support both camelCase (changePct) and snake_case (change_pct)
  if (changePct !== undefined && changePct !== null) {
    lines.push(`涨跌幅: ${formatPercent(changePct)}`);
  }

  const change = data.change;
  if (change !== undefined && change !== null) {
    const sign = change > 0 ? '+' : '';
    lines.push(`涨跌额: ${sign}${formatNumber(change, 2)} 元`);
  }

  if (data.open !== undefined && data.open !== null) {
    lines.push(`今开: ${formatNumber(data.open, 2)} 元`);
  }

  if (data.high !== undefined && data.high !== null) {
    lines.push(`最高: ${formatNumber(data.high, 2)} 元`);
  }

  if (data.low !== undefined && data.low !== null) {
    lines.push(`最低: ${formatNumber(data.low, 2)} 元`);
  }

  // Support both camelCase (prevClose) and snake_case (prev_close)
  // prevClose already declared at line 47
  if (prevClose !== undefined && prevClose !== null) {
    lines.push(`昨收: ${formatNumber(prevClose, 2)} 元`);
  }

  if (data.volume !== undefined && data.volume !== null) {
    const volumeInWan = data.volume / 10000;
    lines.push(`成交量: ${formatNumber(volumeInWan, 0)} 万股`);
  }

  if (data.amount !== undefined && data.amount !== null) {
    const amountInYi = data.amount / 100000000;
    lines.push(`成交额: ${formatNumber(amountInYi, 2)} 亿元`);
  }

  // Data freshness note with timestamp/trade_date
  if (isRealtime) {
    if (data.timestamp) {
      lines.push(`\n数据时间: ${data.timestamp}`);
    }

    const now = new Date();
    const hour = now.getHours();
    const minute = now.getMinutes();
    const isTrading =
      (hour === 9 && minute >= 30) ||
      (hour >= 10 && hour < 11) ||
      (hour === 11 && minute < 30) ||
      (hour >= 13 && hour < 15);

    if (isTrading) {
      lines.push('💡 当前处于交易时段，数据为实时行情');
    } else {
      lines.push('💡 当前非交易时段，显示最新成交价');
    }
  } else if (isFallback) {
    if (data.trade_date) {
      lines.push(`\n交易日期: ${data.trade_date}`);
    }
    lines.push('⚠️ 实时行情获取失败，显示数据库最新收盘价');
  }

  return lines.join('\n');
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
    // RSI - API returns rsi14
    const rsi = factors.rsi14 ?? factors.rsi;
    if (rsi !== undefined && rsi !== null) {
      technicalFactors['RSI(14)'] = formatNumber(rsi, 2);
    }
    if (factors.macd !== undefined && factors.macd !== null) {
      technicalFactors['MACD'] = formatNumber(factors.macd, 4);
    }
    if (factors.macd_signal !== undefined && factors.macd_signal !== null) {
      technicalFactors['MACD信号线'] = formatNumber(factors.macd_signal, 4);
    }
    // MACD histogram - API returns macd_histogram
    const macdHist = factors.macd_histogram ?? factors.macd_hist;
    if (macdHist !== undefined && macdHist !== null) {
      technicalFactors['MACD柱'] = formatNumber(macdHist, 4);
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
    // Bollinger Bands - API returns bollinger_upper/middle/lower
    const bollUpper = factors.bollinger_upper ?? factors.boll_upper;
    if (bollUpper !== undefined && bollUpper !== null) {
      technicalFactors['布林上轨'] = formatNumber(bollUpper, 2);
    }
    const bollMid = factors.bollinger_middle ?? factors.boll_mid;
    if (bollMid !== undefined && bollMid !== null) {
      technicalFactors['布林中轨'] = formatNumber(bollMid, 2);
    }
    const bollLower = factors.bollinger_lower ?? factors.boll_lower;
    if (bollLower !== undefined && bollLower !== null) {
      technicalFactors['布林下轨'] = formatNumber(bollLower, 2);
    }
    // Moving averages
    if (factors.ma5 !== undefined && factors.ma5 !== null) {
      technicalFactors['MA5'] = formatNumber(factors.ma5, 2);
    }
    if (factors.ma10 !== undefined && factors.ma10 !== null) {
      technicalFactors['MA10'] = formatNumber(factors.ma10, 2);
    }
    if (factors.ma20 !== undefined && factors.ma20 !== null) {
      technicalFactors['MA20'] = formatNumber(factors.ma20, 2);
    }
    // ATR
    const atr = factors.atr14 ?? factors.atr;
    if (atr !== undefined && atr !== null) {
      technicalFactors['ATR(14)'] = formatNumber(atr, 2);
    }
    // Volume indicators
    if (factors.volume_ma5 !== undefined && factors.volume_ma5 !== null) {
      technicalFactors['成交量MA5'] = formatNumber(factors.volume_ma5, 0);
    }
    if (factors.volume_ratio !== undefined && factors.volume_ratio !== null) {
      technicalFactors['量比'] = formatNumber(factors.volume_ratio, 2);
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
    // FSCORE and Earnings Quality (Piotroski fundamental factors)
    if (factors.fscore !== undefined && factors.fscore !== null) {
      const fscore = factors.fscore;
      const label = fscore >= 7 ? '🟢' : fscore >= 4 ? '🟡' : '🔴';
      fundamentalFactors[`Piotroski F-Score`] = `${fscore}/9 ${label}`;
    }
    if (factors.earnings_quality !== undefined && factors.earnings_quality !== null) {
      const eq = factors.earnings_quality;
      const label = eq >= 300 ? '🟢' : eq >= 200 ? '🟡' : '🔴';
      fundamentalFactors[`盈利质量评分`] = `${formatNumber(eq, 1)}/400 ${label}`;
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
 * Format factor report generation result into readable text
 */
export function formatFactorReport(result: {
  success: boolean;
  reports?: Array<{
    factor: string;
    success: boolean;
    report_path?: string;
    file_size?: number;
    url?: string;
    error?: string;
  }>;
  total?: number;
  success_count?: number;
  failed_count?: number;
  method?: string;
  period?: { start: string; end: string };
  universe_size?: number;
  error?: string;
}): string {
  const lines: string[] = [];

  if (!result.success) {
    lines.push(`❌ 生成因子报告失败: ${result.error || '未知错误'}`);
    return lines.join('\n');
  }

  lines.push(`📊 因子分析 HTML 报告生成完成`);
  lines.push('');
  lines.push(`总计: ${result.total} 个因子`);
  lines.push(`✅ 成功: ${result.success_count}`);
  if (result.failed_count && result.failed_count > 0) {
    lines.push(`❌ 失败: ${result.failed_count}`);
  }
  lines.push(`分析方法: ${result.method === 'alphalens' ? '专业分析（alphalens）' : '基础分析'}`);

  if (result.period) {
    lines.push(`时间范围: ${result.period.start} ~ ${result.period.end}`);
  }

  if (result.universe_size) {
    lines.push(`股票池大小: ${result.universe_size} 只`);
  }

  lines.push('');
  lines.push('【报告详情】');

  if (result.reports && result.reports.length > 0) {
    result.reports.forEach((report, index) => {
      lines.push(`${index + 1}. ${report.factor}`);

      if (report.success) {
        lines.push(`   ✅ 报告生成成功`);
        if (report.report_path) {
          lines.push(`   📄 文件路径: ${report.report_path}`);
        }
        if (report.file_size) {
          const sizeKB = (report.file_size / 1024).toFixed(1);
          lines.push(`   📦 文件大小: ${sizeKB} KB`);
        }
        if (report.url) {
          lines.push(`   🔗 浏览器访问: ${report.url}`);
        }
      } else {
        lines.push(`   ❌ 生成失败: ${report.error || '未知错误'}`);
      }

      lines.push('');
    });
  }

  lines.push('💡 提示: 可在浏览器中打开 HTML 文件查看完整的可视化报告');
  lines.push('   报告包含: IC 时间序列图、因子分层收益图、累计收益曲线、换手率分析等');

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
 * Format factor analysis result into readable text (v2 enhanced - alphalens)
 */
export function formatFactorAnalysis(analysis: import('./types.js').FactorAnalysis): string {
  const lines: string[] = [];

  if (!analysis.success || !analysis.factors || analysis.factors.length === 0) {
    return '因子分析失败或无结果';
  }

  // 标题
  const methodText = analysis.method === 'alphalens' ? '专业分析（alphalens）' : '基础分析';
  lines.push(`因子分析结果 - ${methodText}（共 ${analysis.factors.length} 个因子）`);

  if (analysis.period) {
    lines.push(`分析区间: ${analysis.period.start} ~ ${analysis.period.end}`);
  }

  if (analysis.universe_size) {
    lines.push(`股票池规模: ${analysis.universe_size}`);
  }

  lines.push('');

  for (const factor of analysis.factors) {
    lines.push(`【${factor.name}】`);

    // alphalens 增强分析
    if (factor.ic_analysis) {
      lines.push('  ► IC 分析:');
      lines.push(`    平均IC: ${formatNumber(factor.ic_analysis.ic_mean, 4)}`);
      lines.push(`    IC标准差: ${formatNumber(factor.ic_analysis.ic_std, 4)}`);
      lines.push(`    信息比率(IR): ${formatNumber(factor.ic_analysis.ic_ir, 4)}`);
      lines.push(`    t统计量: ${formatNumber(factor.ic_analysis.t_stat, 2)}`);
      lines.push(`    p值: ${formatNumber(factor.ic_analysis.p_value, 4)}`);

      if (factor.ic_analysis.ic_by_period) {
        lines.push('    多周期IC:');
        for (const [period, stats] of Object.entries(factor.ic_analysis.ic_by_period)) {
          lines.push(`      ${period}: ${formatNumber(stats.mean, 4)} (±${formatNumber(stats.std, 4)})`);
        }
      }
    }

    // 分层收益分析
    if (factor.returns_analysis) {
      lines.push('  ► 分层收益:');
      if (factor.returns_analysis.mean_return_spread) {
        for (const [period, spread] of Object.entries(factor.returns_analysis.mean_return_spread)) {
          lines.push(`    ${period}多空价差: ${formatPercent(spread * 100, 2)}`);
        }
      }

      // 显示第一个周期的分位数收益
      if (factor.returns_analysis.mean_return_by_quantile) {
        const firstPeriod = Object.keys(factor.returns_analysis.mean_return_by_quantile)[0];
        if (firstPeriod) {
          const quantiles = factor.returns_analysis.mean_return_by_quantile[firstPeriod];
          const quantileStr = Object.entries(quantiles)
            .map(([q, ret]) => `${q}:${formatPercent((ret as number) * 100, 2)}`)
            .join(', ');
          lines.push(`    ${firstPeriod}分位数收益: ${quantileStr}`);
        }
      }
    }

    // 换手率分析
    if (factor.turnover_analysis) {
      lines.push('  ► 换手率:');
      lines.push(`    平均换手率: ${formatPercent(factor.turnover_analysis.mean_turnover * 100, 2)}`);
      if (factor.turnover_analysis.autocorrelation) {
        const autocorrStr = Object.entries(factor.turnover_analysis.autocorrelation)
          .map(([period, corr]) => `${period}:${formatNumber(corr as number, 3)}`)
          .join(', ');
        lines.push(`    自相关性: ${autocorrStr}`);
      }
    }

    // 覆盖率分析（新增）
    if (factor.coverage_analysis) {
      lines.push('  ► 覆盖率:');
      const coverage = factor.coverage_analysis.coverage_ratio;
      const qualityText = coverage > 0.9 ? '优秀' : coverage > 0.7 ? '良好' : '较差';
      lines.push(`    总体覆盖率: ${formatPercent(coverage * 100, 2)} (${qualityText})`);
      lines.push(`    有效样本: ${factor.coverage_analysis.valid_samples} / ${factor.coverage_analysis.total_samples}`);
      if (factor.coverage_analysis.missing_samples > 0) {
        lines.push(`    缺失样本: ${factor.coverage_analysis.missing_samples}`);
      }

      // 按日期覆盖率（可选，如果数据太多则不显示）
      if (factor.coverage_analysis.coverage_by_date) {
        const dateCount = Object.keys(factor.coverage_analysis.coverage_by_date).length;
        if (dateCount <= 5) {
          lines.push('    按日期覆盖率:');
          for (const [date, ratio] of Object.entries(factor.coverage_analysis.coverage_by_date)) {
            lines.push(`      ${date}: ${formatPercent((ratio as number) * 100, 1)}`);
          }
        }
      }
    }

    // 单调性分析（新增）
    if (factor.monotonicity_analysis) {
      lines.push('  ► 单调性:');
      const mono = factor.monotonicity_analysis.monotonicity_ratio;
      const qualityText = mono > 0.8 ? '优秀' : mono > 0.6 ? '良好' : mono > 0.4 ? '一般' : '较差';
      const statusIcon = factor.monotonicity_analysis.is_monotonic ? '✓' : '✗';
      lines.push(`    单调性比例: ${formatPercent(mono * 100, 2)} (${qualityText}) ${statusIcon}`);
      lines.push(`    方向: ${factor.monotonicity_analysis.direction === 'increasing' ? '单调递增' : factor.monotonicity_analysis.direction === 'decreasing' ? '单调递减' : '混合'}`);
      lines.push(`    单调期数: ${factor.monotonicity_analysis.monotonic_periods} / ${factor.monotonicity_analysis.total_periods}`);

      if (factor.monotonicity_analysis.violations_count > 0) {
        lines.push(`    违反单调性: ${factor.monotonicity_analysis.violations_count} 次`);

        // 显示前2个违反案例
        if (factor.monotonicity_analysis.violations_sample && factor.monotonicity_analysis.violations_sample.length > 0) {
          lines.push('    示例（前2次）:');
          for (const violation of factor.monotonicity_analysis.violations_sample.slice(0, 2)) {
            const returnsStr = violation.returns.map((r: number) => formatPercent(r * 100, 1)).join(' → ');
            lines.push(`      ${violation.date}: ${returnsStr}`);
          }
        }
      }
    }

    // 向后兼容：fallback 模式字段
    if (factor.ic_daily !== undefined) {
      lines.push(`  日度IC: ${formatNumber(factor.ic_daily, 4)}`);
      if (factor.ic_weekly !== undefined) lines.push(`  周度IC: ${formatNumber(factor.ic_weekly, 4)}`);
      if (factor.ic_monthly !== undefined) lines.push(`  月度IC: ${formatNumber(factor.ic_monthly, 4)}`);
      if (factor.stability !== undefined) {
        lines.push(`  稳定性: ${formatNumber(factor.stability, 4)}`);
      }

      if (factor.decay_curve && factor.decay_curve.length > 0) {
        const MAX_DECAY_DISPLAY = 10;
        const decayStr = factor.decay_curve
          .slice(0, MAX_DECAY_DISPLAY)
          .map(v => formatNumber(v, 3))
          .join(', ');
        lines.push(`  衰减曲线: [${decayStr}${factor.decay_curve.length > MAX_DECAY_DISPLAY ? ', ...' : ''}]`);
      }
    }

    // 共同字段（保留向后兼容）
    if (!factor.coverage_analysis && factor.coverage !== undefined) {
      lines.push(`  覆盖率: ${formatPercent(factor.coverage * 100, 2)}`);
    }
    if (factor.data_points) {
      lines.push(`  数据点数: ${factor.data_points}`);
    }

    lines.push('');
  }

  // 注释和警告
  if (analysis.note) {
    lines.push(`📝 ${analysis.note}`);
  }
  if (analysis.warning) {
    lines.push(`⚠️  ${analysis.warning}`);
  }

  return lines.join('\n');
}

/**
 * 格式化策略信号为可读文本
 */
export function formatStrategySignal(signal: import('./types.js').StrategySignal): string {
  const lines: string[] = [];

  // 标题
  lines.push(`【策略信号】${signal.name} (${signal.symbol})`);
  lines.push(`策略: ${signal.strategy}`);
  lines.push(`时间: ${signal.timestamp}`);
  lines.push('');

  // 信号
  const actionMap = { buy: '买入', sell: '卖出', hold: '持有' };
  const actionText = actionMap[signal.action] || signal.action;
  lines.push(`信号: ${actionText}`);
  lines.push(`置信度: ${formatPercent(signal.confidence * 100, 1)}`);
  lines.push(`理由: ${signal.reason}`);
  lines.push('');

  // 风险管理
  if (signal.risk_management) {
    lines.push('【风险管理】');

    // 止损
    if (signal.risk_management.stop_loss) {
      const sl = signal.risk_management.stop_loss;
      lines.push(`止损价格: ${formatNumber(sl.price, 2)} 元`);

      if (sl.type === 'atr' && sl.params.atr_value !== undefined && sl.params.atr_multiplier !== undefined) {
        lines.push(`  类型: ATR止损 (${sl.params.atr_multiplier}倍ATR)`);
        lines.push(`  ATR值: ${formatNumber(sl.params.atr_value, 2)}`);
      } else if (sl.type === 'percent' && sl.params.percent !== undefined) {
        lines.push(`  类型: 固定百分比止损 (${formatPercent(sl.params.percent)})`);
      } else if (sl.type === 'trailing' && sl.params.trailing_percent !== undefined) {
        lines.push(`  类型: 追踪止损 (${formatPercent(sl.params.trailing_percent)})`);
      } else if (sl.type === 'fixed') {
        lines.push(`  类型: 固定价格止损`);
      }
    }

    // 仓位管理
    if (signal.risk_management.position_sizing) {
      const ps = signal.risk_management.position_sizing;
      lines.push('');
      lines.push('仓位建议:');

      if (ps.method === 'kelly' && ps.params.win_rate !== undefined && ps.params.profit_loss_ratio !== undefined) {
        lines.push(`  方法: Kelly准则`);
        lines.push(`  胜率: ${formatPercent(ps.params.win_rate, 1)}`);
        lines.push(`  盈亏比: ${formatNumber(ps.params.profit_loss_ratio, 2)}`);
        lines.push(`  Kelly系数: ${formatNumber(ps.params.kelly_fraction || 0.25, 2)}`);
        lines.push(`  说明: 需要根据账户余额计算具体仓位`);
      } else if (ps.method === 'fixed_percent' && ps.params.percent !== undefined) {
        lines.push(`  方法: 固定比例`);
        lines.push(`  比例: ${formatPercent(ps.params.percent)}`);
      } else if (ps.method === 'fixed_shares' && ps.params.shares !== undefined) {
        lines.push(`  方法: 固定股数`);
        lines.push(`  股数: ${formatNumber(ps.params.shares, 0)} 股`);
      }
    }

    // 止盈（可选）
    if (signal.risk_management.take_profit) {
      const tp = signal.risk_management.take_profit;
      lines.push('');
      lines.push(`止盈价格: ${formatNumber(tp.price, 2)} 元`);
    }

    lines.push('');
  }

  // 技术指标
  if (signal.indicators && Object.keys(signal.indicators).length > 0) {
    lines.push('【技术指标】');
    for (const [key, value] of Object.entries(signal.indicators)) {
      const displayName = key.toUpperCase();
      lines.push(`${displayName}: ${formatNumber(value, 2)}`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

/**
 * Helper function to format date field, handling NaN values
 */
function formatDateField(dateStr: string | number | null | undefined): string {
  if (dateStr === null || dateStr === undefined) return '未公布';

  const str = String(dateStr).toLowerCase();
  // Check for NaN, nan, null, undefined, empty string
  if (str === 'nan' || str === 'null' || str === 'undefined' || str.trim() === '') {
    return '未公布';
  }

  return String(dateStr);
}

/**
 * Format dividend data into readable text
 */
export function formatDividendData(data: import('./types.js').DividendResponse, mode: string): string {
  if (!data.success) {
    return `查询失败: ${data.error || '未知错误'}`;
  }

  if (mode === 'single') {
    const { symbol, name, dividends, summary } = data;
    let output = `【${name} (${symbol}) 分红历史】\n\n`;

    if (summary) {
      output += `连续分红: ${summary.consecutive_years}年\n`;
      output += `平均股息率: ${summary.avg_yield.toFixed(2)}%\n`;
      output += `累计每股派息: ${summary.total_cash_dividend.toFixed(2)}元\n\n`;
    }

    output += `近期分红记录:\n`;
    dividends?.slice(0, 5).forEach(d => {
      output += `  ${d.fiscal_year}年: 每股${d.cash_per_share.toFixed(2)}元, `;
      output += `股息率${d.dividend_yield.toFixed(2)}%, `;
      output += `除权日${formatDateField(d.ex_dividend_date)}, ${d.status}\n`;
    });

    if (dividends && dividends.length > 5) {
      output += `\n... 共 ${dividends.length} 条记录\n`;
    }

    return output;
  }

  if (mode === 'screen') {
    const { total, stocks } = data;
    let output = `【高股息股票筛选结果】共 ${total} 只\n\n`;

    stocks?.slice(0, 20).forEach((s, i) => {
      output += `${i + 1}. ${s.name} (${s.symbol})\n`;
      output += `   股息率: ${s.latest_yield.toFixed(2)}%, `;
      output += `连续分红: ${s.consecutive_years}年, `;
      output += `平均分红率: ${s.avg_payout_ratio.toFixed(1)}%\n`;
    });

    if (stocks && stocks.length > 20) {
      output += `\n... 仅显示前20只，共 ${stocks.length} 只\n`;
    }

    return output;
  }

  if (mode === 'calendar') {
    const { period, event_type, total, events } = data;
    let output = `【分红日历 - ${event_type}】\n`;
    output += `时间范围: ${period}\n`;
    output += `共 ${total} 只股票\n\n`;

    events?.forEach(e => {
      output += `${e.date} - ${e.name} (${e.symbol})\n`;
      output += `  每股派息: ${e.cash_per_share.toFixed(2)}元, 股息率: ${e.dividend_yield.toFixed(2)}%\n`;
    });

    return output;
  }

  return '未知查询模式';
}

/**
 * Format single strategy execution signal into readable text
 */
export function formatSingleSignal(signal: import('./types.js').StrategyExecutionSignal): string {
  const lines: string[] = [];

  // Signal type emoji
  const signalEmoji = {
    'BUY': '🟢',
    'SELL': '🔴',
    'HOLD': '🟡',
  };

  const signalText = {
    'BUY': '买入',
    'SELL': '卖出',
    'HOLD': '持有',
  };

  // Header
  lines.push(`${signalEmoji[signal.signal_type]} 【策略信号】${signal.symbol}`);
  if (signal.signal_id) {
    lines.push(`信号ID: ${signal.signal_id}`);
  }
  lines.push('');

  // Signal details
  lines.push(`信号类型: ${signalText[signal.signal_type]}`);
  lines.push(`置信度: ${formatPercent(signal.confidence * 100)}`);
  lines.push(`入场价格: ${formatNumber(signal.entry_price, 2)} 元`);
  lines.push('');

  // Risk management
  if (signal.stop_loss || signal.target_price || signal.position_size) {
    lines.push('【风险管理】');
    if (signal.stop_loss) {
      lines.push(`止损价格: ${formatNumber(signal.stop_loss, 2)} 元`);
    }
    if (signal.target_price) {
      lines.push(`目标价格: ${formatNumber(signal.target_price, 2)} 元`);
    }
    if (signal.position_size) {
      lines.push(`建议仓位: ${formatNumber(signal.position_size, 0)} 股`);
    }
    lines.push('');
  }

  // Technical indicators
  if (signal.indicators && Object.keys(signal.indicators).length > 0) {
    lines.push('【技术指标】');
    for (const [key, value] of Object.entries(signal.indicators)) {
      const displayName = key.toUpperCase();
      lines.push(`${displayName}: ${formatNumber(value, 2)}`);
    }
  }

  return lines.join('\n');
}

/**
 * Format batch execution result into readable text with signal distribution table
 */
export function formatBatchSignals(result: import('./types.js').BatchExecutionResult): string {
  const lines: string[] = [];

  lines.push('【批量执行完成】');
  lines.push('');

  // Summary statistics
  lines.push('执行统计:');
  lines.push(`  总数: ${result.summary.total}`);
  lines.push(`  成功: ${result.summary.success}`);
  lines.push(`  失败: ${result.summary.failed}`);
  lines.push(`  耗时: ${formatNumber(result.summary.duration_ms / 1000, 2)} 秒`);
  lines.push('');

  // Signal distribution table
  lines.push('信号分布:');
  lines.push(`  买入: ${result.summary.buy}`);
  lines.push(`  卖出: ${result.summary.sell}`);
  lines.push(`  持有: ${result.summary.hold}`);
  lines.push('');

  // Errors
  if (result.errors.length > 0) {
    lines.push('执行错误:');
    result.errors.forEach(err => {
      lines.push(`  ${err.symbol}: ${err.error}`);
    });
    lines.push('');
  }

  // Signal list
  if (result.signals.length > 0) {
    lines.push(`信号列表 (共 ${result.signals.length} 个):`);
    result.signals.forEach((signal, index) => {
      const signalText = {
        'BUY': '买入',
        'SELL': '卖出',
        'HOLD': '持有',
      };
      lines.push(`  ${index + 1}. ${signal.symbol} - ${signalText[signal.signal_type]} (置信度: ${formatPercent(signal.confidence * 100)})`);
    });
  }

  return lines.join('\n');
}

/**
 * Format pipeline execution result into readable text with rejection reasons
 */
export function formatPipelineResult(result: import('./types.js').PipelineExecutionResult): string {
  const lines: string[] = [];

  lines.push('【策略流水线执行完成】');
  lines.push('');

  // Execution summary
  lines.push(`执行日期: ${result.execution_date}`);
  lines.push(`执行耗时: ${formatNumber(result.duration_ms / 1000, 2)} 秒`);
  lines.push('');

  // Signal statistics
  lines.push('信号统计:');
  lines.push(`  生成信号: ${result.signals_generated}`);
  lines.push(`  通过: ${result.signals_approved}`);
  lines.push(`  拒绝: ${result.signals_rejected}`);
  lines.push(`  创建订单: ${result.orders_created}`);
  lines.push('');

  // Rejection reasons distribution
  if (Object.keys(result.rejection_reasons).length > 0) {
    lines.push('拒绝原因分布:');
    const sortedReasons = Object.entries(result.rejection_reasons)
      .sort((a, b) => b[1] - a[1]);
    sortedReasons.forEach(([reason, count]) => {
      lines.push(`  ${reason}: ${count}`);
    });
    lines.push('');
  }

  // Orders created
  if (result.orders.length > 0) {
    lines.push(`订单列表 (共 ${result.orders.length} 个):`);
    result.orders.forEach((order, index) => {
      const sideText = order.side === 'BUY' ? '买入' : '卖出';
      lines.push(`  ${index + 1}. ${order.symbol} - ${sideText} @ ${formatNumber(order.price, 2)} 元`);
      if (order.quantity) {
        lines.push(`     数量: ${formatNumber(order.quantity, 0)} 股`);
      }
    });
  }

  return lines.join('\n');
}

/**
 * Format risk metrics into readable text
 */
export function formatRiskMetrics(metrics: any): string {
  const lines: string[] = [];

  lines.push('📊 风险与收益指标');
  lines.push('');

  // 收益指标
  lines.push('【收益指标】');
  if (metrics.annual_return !== undefined) {
    lines.push(`  年化收益率: ${formatPercent(metrics.annual_return * 100, 2)}`);
  }
  if (metrics.annual_volatility !== undefined) {
    lines.push(`  年化波动率: ${formatPercent(metrics.annual_volatility * 100, 2)}`);
  }
  lines.push('');

  // 风险调整收益
  lines.push('【风险调整收益】');
  if (metrics.sharpe_ratio !== undefined) {
    const sharpeColor = metrics.sharpe_ratio > 1 ? '✅' : metrics.sharpe_ratio > 0 ? '⚠️' : '❌';
    lines.push(`  ${sharpeColor} 夏普比率: ${formatNumber(metrics.sharpe_ratio, 4)}`);
  }
  if (metrics.sortino_ratio !== undefined) {
    const sortinoColor = metrics.sortino_ratio > 1 ? '✅' : metrics.sortino_ratio > 0 ? '⚠️' : '❌';
    lines.push(`  ${sortinoColor} 索提诺比率: ${formatNumber(metrics.sortino_ratio, 4)}`);
  }
  if (metrics.calmar_ratio !== undefined) {
    const calmarColor = metrics.calmar_ratio > 1 ? '✅' : metrics.calmar_ratio > 0 ? '⚠️' : '❌';
    lines.push(`  ${calmarColor} 卡尔马比率: ${formatNumber(metrics.calmar_ratio, 4)}`);
  }
  lines.push('');

  // 回撤指标
  lines.push('【回撤指标】');
  if (metrics.max_drawdown !== undefined) {
    const ddColor = metrics.max_drawdown > -0.1 ? '✅' : metrics.max_drawdown > -0.2 ? '⚠️' : '❌';
    lines.push(`  ${ddColor} 最大回撤: ${formatPercent(metrics.max_drawdown * 100, 2)}`);
  }
  lines.push('');

  // Alpha/Beta 分析
  if (metrics.alpha !== undefined && metrics.beta !== undefined) {
    lines.push('【Alpha/Beta 分析】');
    const alphaColor = metrics.alpha > 0 ? '✅' : '❌';
    lines.push(`  ${alphaColor} Alpha: ${formatPercent(metrics.alpha * 100, 4)}`);
    lines.push(`  Beta: ${formatNumber(metrics.beta, 4)}`);
    lines.push('');
  }

  // 尾部风险
  lines.push('【尾部风险】');
  if (metrics.var_95 !== undefined) {
    lines.push(`  VaR (95%): ${formatPercent(metrics.var_95 * 100, 2)}`);
  }
  if (metrics.cvar_95 !== undefined) {
    lines.push(`  CVaR (95%): ${formatPercent(metrics.cvar_95 * 100, 2)}`);
  }

  // 指标说明
  lines.push('');
  lines.push('💡 指标说明:');
  lines.push('  夏普比率 > 1: 优秀，0-1: 良好，< 0: 差');
  lines.push('  索提诺比率: 只惩罚下行波动，比夏普更合理');
  lines.push('  卡尔马比率: 收益/最大回撤，衡量回撤调整后收益');
  lines.push('  VaR: 95%置信度下的最大损失');
  lines.push('  CVaR: 超过VaR的平均损失（尾部期望）');

  return lines.join('\n');
}

/**
 * Format backtest result into readable text with summary
 */
export function formatBacktestResult(result: any): string {
  const lines: string[] = [];

  lines.push('📈 指标回测结果');
  lines.push('');

  // Summary metrics — merge top-level & summary, support both camelCase & snake_case (Bug 3 fix)
  // Python backend returns camelCase (totalReturn, winRate), but legacy paths use snake_case
  const s = { ...result, ...(result.summary || {}) };
  const g = (camel: string, snake: string) => s[camel] ?? s[snake];

  const totalReturn = g('totalReturn', 'total_return');
  const annualReturn = g('annualReturn', 'annual_return');
  const sharpeRatio = g('sharpeRatio', 'sharpe_ratio');
  const maxDrawdown = g('maxDrawdown', 'max_drawdown');
  const winRate = g('winRate', 'win_rate');
  const profitLossRatio = g('profitLossRatio', 'profit_loss_ratio');
  const profitFactor = g('profitFactor', 'profit_factor');

  const hasSummary = [totalReturn, sharpeRatio, maxDrawdown, winRate].some(v => v !== undefined);
  if (hasSummary) {
    lines.push('【回测摘要】');

    if (totalReturn !== undefined) {
      const returnColor = totalReturn > 0 ? '✅' : '❌';
      lines.push(`  ${returnColor} 总收益率: ${formatPercent(totalReturn * 100, 2)}`);
    }

    if (annualReturn !== undefined) {
      lines.push(`  年化收益率: ${formatPercent(annualReturn * 100, 2)}`);
    }

    if (sharpeRatio !== undefined) {
      const sharpeColor = sharpeRatio > 1 ? '✅' : sharpeRatio > 0 ? '⚠️' : '❌';
      lines.push(`  ${sharpeColor} 夏普比率: ${formatNumber(sharpeRatio, 2)}`);
    }

    if (maxDrawdown !== undefined) {
      const ddColor = maxDrawdown > -0.1 ? '✅' : maxDrawdown > -0.2 ? '⚠️' : '❌';
      lines.push(`  ${ddColor} 最大回撤: ${formatPercent(maxDrawdown * 100, 2)}`);
    }

    if (winRate !== undefined) {
      const winColor = winRate > 0.6 ? '✅' : winRate > 0.5 ? '⚠️' : '❌';
      lines.push(`  ${winColor} 胜率: ${formatPercent(winRate * 100, 1)}`);
    }

    if (profitLossRatio !== undefined) {
      lines.push(`  盈亏比: ${formatNumber(profitLossRatio, 2)}`);
    } else if (profitFactor !== undefined) {
      lines.push(`  盈亏比: ${formatNumber(profitFactor, 2)}`);
    }

    lines.push('');
  }

  // Trade statistics
  if (result.trades && Array.isArray(result.trades)) {
    lines.push('【交易统计】');
    lines.push(`  总交易次数: ${result.trades.length}`);

    // Python backend returns 'pnl' (profit & loss amount) and 'return' (decimal return)
    // NOT 'profit' or 'profit_pct' — Bug 1 fix
    const profitTrades = result.trades.filter((t: any) => (t.pnl ?? t.profit ?? 0) > 0).length;
    const lossTrades = result.trades.filter((t: any) => (t.pnl ?? t.profit ?? 0) < 0).length;
    lines.push(`  盈利交易: ${profitTrades} 次`);
    lines.push(`  亏损交易: ${lossTrades} 次`);

    if (result.trades.length > 0) {
      const avgReturn = result.trades.reduce((sum: number, t: any) => sum + ((t.return ?? t.profit_pct ?? 0) * 100), 0) / result.trades.length;
      lines.push(`  平均收益率: ${formatPercent(avgReturn, 2)}`);
    }

    lines.push('');
  }

  // Equity curve info
  if (result.equity_curve && Array.isArray(result.equity_curve)) {
    lines.push('【权益曲线】');
    lines.push(`  数据点数: ${result.equity_curve.length}`);

    if (result.equity_curve.length > 0) {
      const firstEquity = result.equity_curve[0].equity;
      const lastEquity = result.equity_curve[result.equity_curve.length - 1].equity;
      const totalReturn = ((lastEquity - firstEquity) / firstEquity) * 100;
      lines.push(`  初始权益: ${formatNumber(firstEquity, 2)} 元`);
      lines.push(`  最终权益: ${formatNumber(lastEquity, 2)} 元`);
      lines.push(`  权益增长: ${formatPercent(totalReturn, 2)}`);
    }

    lines.push('');
  }

  // Additional metrics
  if (result.metrics) {
    lines.push('【其他指标】');
    const m = result.metrics;

    if (m.volatility !== undefined) {
      lines.push(`  年化波动率: ${formatPercent(m.volatility * 100, 2)}`);
    }

    if (m.sortino_ratio !== undefined) {
      lines.push(`  索提诺比率: ${formatNumber(m.sortino_ratio, 2)}`);
    }

    if (m.calmar_ratio !== undefined) {
      lines.push(`  卡尔马比率: ${formatNumber(m.calmar_ratio, 2)}`);
    }

    lines.push('');
  }

  lines.push('💡 提示: 完整的交易记录和权益曲线已保存到本地文件');

  return lines.join('\n');
}

/**
 * Format strategy detail into readable text
 */
export function formatStrategyDetail(strategy: any): string {
  const lines: string[] = [];

  lines.push('📋 策略详情');
  lines.push('');

  // Basic info
  lines.push('【基本信息】');
  if (strategy.id) {
    lines.push(`  策略ID: ${strategy.id}`);
  }
  if (strategy.name) {
    lines.push(`  策略名称: ${strategy.name}`);
  }
  if (strategy.description) {
    lines.push(`  描述: ${strategy.description}`);
  }
  if (strategy.created_at) {
    lines.push(`  创建时间: ${strategy.created_at}`);
  }
  if (strategy.updated_at) {
    lines.push(`  更新时间: ${strategy.updated_at}`);
  }
  lines.push('');

  // Strategy type and parameters
  if (strategy.type) {
    lines.push('【策略类型】');
    lines.push(`  类型: ${strategy.type}`);
    lines.push('');
  }

  if (strategy.parameters && Object.keys(strategy.parameters).length > 0) {
    lines.push('【策略参数】');
    for (const [key, value] of Object.entries(strategy.parameters)) {
      lines.push(`  ${key}: ${JSON.stringify(value)}`);
    }
    lines.push('');
  }

  // Lifecycle status
  lines.push('【生命周期】');
  const isActive = strategy.is_active !== undefined ? strategy.is_active : true;
  lines.push(`  状态: ${isActive ? '✅ 活跃' : '❌ 停用'}`);
  const validationStatus = strategy.validation_status ?? '?';
  lines.push(`  验证: ${validationStatus}`);
  const tags = Array.isArray(strategy.tags) ? strategy.tags : [];
  if (tags.length > 0) {
    lines.push(`  标签: ${tags.join(', ')}`);
  }
  if (strategy.strategy_profile && Object.keys(strategy.strategy_profile).length > 0) {
    const profile = strategy.strategy_profile;
    if (profile.strategy_type) lines.push(`  策略类型: ${profile.strategy_type}`);
    if (profile.risk_level) lines.push(`  风险等级: ${profile.risk_level}`);
    if (profile.market_condition) {
      const mc = Array.isArray(profile.market_condition) ? profile.market_condition.join(', ') : profile.market_condition;
      lines.push(`  适用市场: ${mc}`);
    }
    if (profile.stop_loss_pct !== undefined) lines.push(`  止损: ${profile.stop_loss_pct}%`);
    if (profile.take_profit_pct !== undefined) lines.push(`  止盈: ${profile.take_profit_pct}%`);
  }
  lines.push('');

  // Performance summary (if available)
  if (strategy.performance) {
    lines.push('【历史表现】');
    const p = strategy.performance;

    if (p.total_trades !== undefined) {
      lines.push(`  总交易次数: ${p.total_trades}`);
    }
    if (p.win_rate !== undefined) {
      const winColor = p.win_rate > 0.6 ? '✅' : p.win_rate > 0.5 ? '⚠️' : '❌';
      lines.push(`  ${winColor} 胜率: ${formatPercent(p.win_rate * 100, 1)}`);
    }
    if (p.avg_return !== undefined) {
      lines.push(`  平均收益率: ${formatPercent(p.avg_return * 100, 2)}`);
    }
    if (p.sharpe_ratio !== undefined) {
      lines.push(`  夏普比率: ${formatNumber(p.sharpe_ratio, 2)}`);
    }
    lines.push('');
  }

  // Strategy code
  if (strategy.code) {
    lines.push('【策略代码】');
    lines.push('```python');
    lines.push(strategy.code);
    lines.push('```');
    lines.push('');
  }

  // Configuration
  if (strategy.config && Object.keys(strategy.config).length > 0) {
    lines.push('【配置信息】');
    for (const [key, value] of Object.entries(strategy.config)) {
      lines.push(`  ${key}: ${JSON.stringify(value)}`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

/**
 * Format portfolio optimization result
 */
export function formatPortfolioWeights(result: any): string {
  const lines: string[] = [];

  lines.push(`📊 组合优化结果 (${result.method})`);
  lines.push('');

  // 权重分配
  lines.push('【权重分配】');
  
  const weights = Object.entries(result.weights as Record<string, number>)
    .sort((a, b) => b[1] - a[1]);
  
  for (const [symbol, weight] of weights) {
    const weightPct = weight * 100;
    const bar = '█'.repeat(Math.round(weight * 20));
    lines.push(`  ${symbol}: ${formatPercent(weightPct, 2)} ${bar}`);
  }
  
  lines.push('');
  
  // 组合指标
  if (result.expected_return !== undefined || result.risk !== undefined || result.sharpe !== undefined) {
    lines.push('【组合指标】');
    
    if (result.expected_return !== undefined) {
      lines.push(`  预期收益率: ${formatPercent(result.expected_return * 100, 2)}`);
    }
    
    if (result.risk !== undefined) {
      lines.push(`  组合风险: ${formatPercent(result.risk * 100, 2)}`);
    }
    
    if (result.sharpe !== undefined) {
      const sharpeColor = result.sharpe > 1 ? '✅' : result.sharpe > 0 ? '⚠️' : '❌';
      lines.push(`  ${sharpeColor} 夏普比率: ${formatNumber(result.sharpe, 4)}`);
    }
    
    lines.push('');
  }
  
  // 风险贡献（如果有）
  if (result.risk_contributions) {
    lines.push('【风险贡献】');
    
    const contribs = Object.entries(result.risk_contributions as Record<string, number>)
      .sort((a, b) => b[1] - a[1]);
    
    for (const [symbol, contrib] of contribs) {
      lines.push(`  ${symbol}: ${formatPercent(contrib * 100, 4)}`);
    }
    
    lines.push('');
  }
  
  // 优化方法说明
  lines.push('💡 优化方法:');
  if (result.method === 'mean_variance') {
    lines.push('  均值-方差优化（马科维茨模型）');
    lines.push('  目标: 最大化 (收益 - 风险厌恶系数 × 方差)');
  } else if (result.method === 'min_variance') {
    lines.push('  最小方差优化');
    lines.push('  目标: 最小化组合风险');
  } else if (result.method === 'max_sharpe') {
    lines.push('  最大夏普比率优化');
    lines.push('  目标: 最大化 (收益 - 无风险利率) / 风险');
  } else if (result.method === 'risk_parity') {
    lines.push('  风险平价优化');
    lines.push('  目标: 每个资产贡献相同的风险');
  }

  return lines.join('\n');
}
