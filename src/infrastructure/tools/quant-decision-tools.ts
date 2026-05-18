/**
 * Quant Decision Tools - 量化决策工具集
 *
 * 提供高层决策工具，组合多个数据源提供综合分析建议
 */

import { Type } from '@sinclair/typebox';
import type { ToolDefinition } from "./index.js";
import { QuantService } from '../../services/quant/quant-service.js';
import { SignalGenerator } from '../../services/quant/signal-generator.js';
import { FactorLibrary } from '../../services/quant/factor-library.js';
import { StockDBService } from '../../services/data/stock-db-service.js';
import { queryAndFormatExperience } from '../../services/intelligence/experience-query.js';
import { get_stock_realtime_price, get_stock_info } from '../akshare-ts/index.js';

// 初始化服务
const quantService = new QuantService();
const stockDBService = new StockDBService('.pi-invest');
const factorLibrary = new FactorLibrary(stockDBService);
const signalGenerator = new SignalGenerator('.pi-invest/quant/signals', factorLibrary);

/**
 * 辅助函数：计算技术指标
 */
async function calculateTechnicalIndicators(symbol: string) {
  const [rsi, ma5, ma10, ma20, ma60, macd, bb, fundamentals] = await Promise.all([
    factorLibrary.calculateRSIForSymbol(symbol, 14),
    factorLibrary.calculateMAForSymbol(symbol, 5),
    factorLibrary.calculateMAForSymbol(symbol, 10),
    factorLibrary.calculateMAForSymbol(symbol, 20),
    factorLibrary.calculateMAForSymbol(symbol, 60),
    factorLibrary.calculateMACDForSymbol(symbol),
    factorLibrary.calculateBollingerBands(symbol, 20, 2),
    factorLibrary.getFundamentals(symbol)
  ]);

  return {
    rsi,
    ma5,
    ma10,
    ma20,
    ma60,
    macd_dif: macd.dif,
    macd_dea: macd.dea,
    macd_histogram: macd.macd,
    bollinger_upper: bb.upper,
    bollinger_mid: bb.middle,
    bollinger_lower: bb.lower,
    volume_ratio: 1.0,
    atr: 0,
    pe: fundamentals.pe,
    pb: fundamentals.pb,
    roe: fundamentals.roe,
    gross_margin: fundamentals.gross_margin,
    debt_ratio: fundamentals.debt_ratio,
  };
}

/**
 * 辅助函数：评估技术信号
 */
function evaluateTechnicalSignals(tech: any, price: number) {
  const signals: Array<{ signal: string; status: 'positive' | 'negative' | 'neutral'; description: string }> = [];

  // RSI信号
  if (tech.rsi < 30) {
    signals.push({ signal: 'RSI超卖', status: 'positive', description: `RSI(${tech.rsi.toFixed(1)}) - 反弹概率高` });
  } else if (tech.rsi > 70) {
    signals.push({ signal: 'RSI超买', status: 'negative', description: `RSI(${tech.rsi.toFixed(1)}) - 回调风险` });
  }

  // MACD信号
  if (tech.macd_dif > tech.macd_dea && tech.macd_histogram > 0) {
    signals.push({ signal: 'MACD金叉', status: 'positive', description: '趋势转多' });
  } else if (tech.macd_dif < tech.macd_dea && tech.macd_histogram < 0) {
    signals.push({ signal: 'MACD死叉', status: 'negative', description: '趋势转空' });
  }

  // 均线信号
  if (tech.ma5 > tech.ma10 && tech.ma10 > tech.ma20) {
    signals.push({ signal: '均线多头排列', status: 'positive', description: '短中期趋势向上' });
  } else if (tech.ma5 < tech.ma10 && tech.ma10 < tech.ma20) {
    signals.push({ signal: '均线空头排列', status: 'negative', description: '短中期趋势向下' });
  }

  // 布林带信号
  if (price < tech.bollinger_lower) {
    signals.push({ signal: '跌破布林下轨', status: 'positive', description: '超卖反弹机会' });
  } else if (price > tech.bollinger_upper) {
    signals.push({ signal: '突破布林上轨', status: 'negative', description: '超买回调风险' });
  }

  return signals;
}

/**
 * 辅助函数：计算综合评分
 */
function calculateOverallScore(tech: any, signals: any[], quantSignals: any[]) {
  let score = 50; // 基础分

  // RSI评分 (0-20分)
  if (tech.rsi < 30) score += 15;
  else if (tech.rsi < 40) score += 10;
  else if (tech.rsi > 70) score -= 15;
  else if (tech.rsi > 60) score -= 10;

  // MACD评分 (0-15分)
  if (tech.macd_dif > tech.macd_dea && tech.macd_histogram > 0) score += 15;
  else if (tech.macd_dif < tech.macd_dea && tech.macd_histogram < 0) score -= 15;

  // 均线评分 (0-15分)
  if (tech.ma5 > tech.ma10 && tech.ma10 > tech.ma20) score += 15;
  else if (tech.ma5 < tech.ma10 && tech.ma10 < tech.ma20) score -= 15;

  // 量化信号评分 (0-20分)
  const buySignals = quantSignals.filter(s => s.action === 'buy').length;
  const sellSignals = quantSignals.filter(s => s.action === 'sell').length;
  score += (buySignals * 10) - (sellSignals * 10);

  return Math.max(0, Math.min(100, score));
}

/**
 * 1. analyze_stock_quant - 股票量化综合分析
 */
export const analyzeStockQuantTool: ToolDefinition = {
  name: 'analyze_stock_quant',
  label: '股票量化综合分析',
  description: `对单只股票进行量化综合分析，一次调用获取完整的决策建议。

包含内容：
- 技术指标分析（RSI/MACD/均线/布林带）
- 量化策略信号
- 历史经验查询
- 综合评分和建议

适用场景：
- 分析持仓股票
- 评估买入机会
- 验证卖出决策`,

  promptSnippet: '需要量化分析股票时',
  promptGuidelines: [
    '返回技术指标、因子分析、风险评估',
    '结果包含买入/卖出信号和置信度',
    '适用于技术面分析和量化选股'
  ],

  parameters: Type.Object({
    symbol: Type.String({
      description: '股票代码，如 600036.SH 或 000425.SZ'
    }),
    context: Type.Optional(Type.Union([
      Type.Literal('buy'),
      Type.Literal('sell'),
      Type.Literal('hold')
    ], {
      description: '分析场景：buy=买入分析, sell=卖出分析, hold=持有分析（默认buy）'
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { symbol, context = 'buy' } = params;

      // 1. 获取股票基本信息和价格
      const [stockInfoStr, priceDataStr] = await Promise.all([
        get_stock_info(symbol),
        get_stock_realtime_price(symbol)
      ]);

      const stockInfo = JSON.parse(stockInfoStr);
      const priceData = JSON.parse(priceDataStr);
      const stockName = stockInfo?.name || symbol;
      const currentPrice = priceData?.current || 0;

      // 2. 计算技术指标
      const tech = await calculateTechnicalIndicators(symbol);

      // 3. 评估技术信号
      const techSignals = evaluateTechnicalSignals(tech, currentPrice);

      // 4. 获取量化策略信号
      const strategies = await quantService.listStrategies();
      const enabledStrategies = strategies.filter(s => s.enabled);

      const quantSignals = [];
      for (const strategy of enabledStrategies.slice(0, 3)) { // 最多3个策略
        try {
          const signal = await signalGenerator.generateSignal(
            symbol,
            stockName,
            strategy,
            tech,
            currentPrice
          );
          if (signal) {
            quantSignals.push({
              strategy: strategy.name,
              action: signal.action,
              confidence: signal.confidence,
              reason: signal.reason
            });
          }
        } catch (e) {
          // 忽略单个策略的错误
        }
      }

      // 5. 查询历史经验
      let experienceText = '';
      try {
        // 根据技术信号构建场景
        let scenario = '';
        if (tech.rsi < 30) scenario = 'RSI超卖';
        else if (tech.macd_dif > tech.macd_dea) scenario = 'MACD金叉';
        else if (tech.ma5 > tech.ma20) scenario = '均线金叉';

        if (scenario) {
          experienceText = queryAndFormatExperience({ scenario, symbol });
        }
      } catch (e) {
        experienceText = '暂无历史经验数据';
      }

      // 6. 计算综合评分
      const score = calculateOverallScore(tech, techSignals, quantSignals);

      // 7. 生成建议
      let recommendation = '';
      let confidence = 0;
      if (context === 'buy') {
        if (score >= 75) {
          recommendation = '强烈建议买入';
          confidence = 85;
        } else if (score >= 60) {
          recommendation = '适度买入';
          confidence = 70;
        } else if (score >= 50) {
          recommendation = '观察等待';
          confidence = 50;
        } else {
          recommendation = '暂不建议买入';
          confidence = 30;
        }
      } else if (context === 'sell') {
        if (score <= 25) {
          recommendation = '建议卖出';
          confidence = 85;
        } else if (score <= 40) {
          recommendation = '考虑减仓';
          confidence = 70;
        } else {
          recommendation = '继续持有';
          confidence = 60;
        }
      } else {
        recommendation = score >= 60 ? '继续持有' : '考虑减仓';
        confidence = Math.abs(score - 50) + 50;
      }

      // 8. 生成风险提示
      const risks = [];
      if (tech.rsi > 70) risks.push('RSI超买，短期回调风险');
      if (tech.volume_ratio < 0.8) risks.push('成交量不足，需要确认');
      if (techSignals.filter(s => s.status === 'negative').length > 2) {
        risks.push('多个技术指标转弱');
      }

      // 9. 格式化输出
      const summary = `
${stockName}(${symbol}) 量化综合分析
=====================================
综合评分: ${score}/100 ${score >= 60 ? '(偏多)' : score >= 40 ? '(中性)' : '(偏空)'}
建议操作: ${recommendation}
置信度: ${confidence}%

技术面信号:
${techSignals.map(s =>
  `${s.status === 'positive' ? '✓' : s.status === 'negative' ? '✗' : '○'} ${s.signal} - ${s.description}`
).join('\n')}

量化策略触发 (${quantSignals.length}个):
${quantSignals.length > 0
  ? quantSignals.map(s =>
      `- ${s.strategy}: ${s.action === 'buy' ? '买入' : '卖出'}信号 (置信度${(s.confidence * 100).toFixed(0)}%)`
    ).join('\n')
  : '- 暂无策略触发'}

历史经验:
${experienceText || '暂无相关历史经验'}

${risks.length > 0 ? `风险提示:\n${risks.map(r => `- ${r}`).join('\n')}` : ''}

当前价格: ¥${currentPrice.toFixed(2)}
技术指标: RSI=${tech.rsi.toFixed(1)} | MACD=${tech.macd_histogram.toFixed(2)} | MA5=${tech.ma5.toFixed(2)}
`.trim();

      return {
        content: [{ type: "text" as const, text: summary }],
        details: {
          score,
          recommendation,
          confidence,
          technical_signals: techSignals,
          quant_signals: quantSignals,
          indicators: tech,
          price: currentPrice,
          risks
        }
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `分析失败: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 2. compare_stocks_quant - 批量对比股票
 */
export const compareStocksQuantTool: ToolDefinition = {
  name: 'compare_stocks_quant',
  label: '批量对比股票',
  description: `批量分析多只股票的量化评分，用于选股和排序。

返回内容：
- 按评分/信号数排序的股票列表
- 每只股票的综合评分和建议
- 快速对比多只股票的优劣

适用场景：
- 从持仓中筛选优质股
- 对比多个候选标的
- 构建投资组合`,

  parameters: Type.Object({
    symbols: Type.Array(Type.String(), {
      description: '股票代码列表，如 ["600036.SH", "000425.SZ"]'
    }),
    sort_by: Type.Optional(Type.Union([
      Type.Literal('score'),
      Type.Literal('signal_count'),
      Type.Literal('confidence')
    ], {
      description: '排序方式：score=评分, signal_count=信号数, confidence=置信度（默认score）'
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { symbols, sort_by = 'score' } = params;

      // 批量分析
      const results: any[] = [];
      for (const symbol of symbols) {
        try {
          // 复用 analyze_stock_quant 的逻辑
          const result = await (analyzeStockQuantTool.execute as any)(_toolCallId, { symbol, context: 'buy' });
          if (result.details) {
            results.push({
              symbol,
              score: result.details.score || 0,
              recommendation: result.details.recommendation || '未知',
              confidence: result.details.confidence || 0,
              quant_signals: result.details.quant_signals || [],
              technical_signals: result.details.technical_signals || [],
              indicators: result.details.indicators
            });
          }
        } catch (e) {
          // 忽略单个股票的错误
          results.push({
            symbol,
            score: 0,
            recommendation: '分析失败',
            confidence: 0,
            quant_signals: [],
            error: e instanceof Error ? e.message : String(e)
          });
        }
      }

      // 排序
      results.sort((a, b) => {
        if (sort_by === 'score') return (b.score || 0) - (a.score || 0);
        if (sort_by === 'signal_count') return (b.quant_signals?.length || 0) - (a.quant_signals?.length || 0);
        if (sort_by === 'confidence') return (b.confidence || 0) - (a.confidence || 0);
        return 0;
      });

      // 格式化输出
      const summary = `
量化评分排名 (共${results.length}只)
=====================================
${results.map((r, i) => {
  const signalCount = r.quant_signals?.length || 0;
  const buySignals = r.quant_signals?.filter((s: any) => s.action === 'buy').length || 0;
  return `${i + 1}. ${r.symbol} - 评分${r.score} - ${buySignals}个买入信号 - ${r.recommendation}`;
}).join('\n')}

排序方式: ${sort_by === 'score' ? '综合评分' : sort_by === 'signal_count' ? '信号数量' : '置信度'}
`.trim();

      return {
        content: [{ type: "text" as const, text: summary }],
        details: results
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `对比失败: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 3. validate_trade_decision - 验证交易决策
 */
export const validateTradeDecisionTool: ToolDefinition = {
  name: 'validate_trade_decision',
  label: '验证交易决策',
  description: `在执行交易前，验证决策的合理性。

验证内容：
- 技术面是否支持
- 量化信号是否一致
- 历史经验是否有利
- 风险因素评估
- 仓位和止损建议

适用场景：
- 买入前的最后确认
- 卖出决策的验证
- 风险评估`,

  parameters: Type.Object({
    symbol: Type.String({
      description: '股票代码'
    }),
    action: Type.Union([
      Type.Literal('buy'),
      Type.Literal('sell')
    ], {
      description: '交易动作：buy=买入, sell=卖出'
    }),
    price: Type.Number({
      description: '计划交易价格'
    }),
    quantity: Type.Optional(Type.Number({
      description: '计划交易数量（可选）'
    })),
    reason: Type.Optional(Type.String({
      description: '交易理由（可选）'
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { symbol, action, price, quantity, reason } = params;

      // 1. 获取综合分析
      const analysisResult = await (analyzeStockQuantTool.execute as any)(_toolCallId, {
        symbol,
        context: action
      });

      if (!analysisResult.details) {
        return {
          content: [{ type: "text" as const, text: '无法获取分析数据' }],
          details: undefined
        };
      }

      const analysis: any = analysisResult.details;

      // 2. 评估决策合理性
      let isValid = false;
      const supportFactors = [];
      const riskFactors = [];

      if (action === 'buy') {
        // 买入验证
        if ((analysis.score || 0) >= 60) {
          isValid = true;
          supportFactors.push(`综合评分${analysis.score}分，技术面偏多`);
        }

        const buySignals = (analysis.quant_signals || []).filter((s: any) => s.action === 'buy');
        if (buySignals.length >= 2) {
          supportFactors.push(`${buySignals.length}个量化策略触发买入信号`);
        } else if (buySignals.length === 0) {
          riskFactors.push('无量化策略支持');
        }

        const positiveTech = (analysis.technical_signals || []).filter((s: any) => s.status === 'positive');
        if (positiveTech.length >= 2) {
          supportFactors.push(`技术面: ${positiveTech.map((s: any) => s.signal).join('、')}`);
        }

        // 风险检查
        if (analysis.indicators?.rsi > 70) {
          riskFactors.push('RSI超买，短期回调风险');
        }
        if ((analysis.score || 0) < 50) {
          riskFactors.push('综合评分偏低，建议谨慎');
        }
      } else {
        // 卖出验证
        if ((analysis.score || 0) <= 40) {
          isValid = true;
          supportFactors.push(`综合评分${analysis.score}分，技术面转弱`);
        }

        const sellSignals = (analysis.quant_signals || []).filter((s: any) => s.action === 'sell');
        if (sellSignals.length >= 1) {
          supportFactors.push(`${sellSignals.length}个量化策略触发卖出信号`);
        }

        const negativeTech = (analysis.technical_signals || []).filter((s: any) => s.status === 'negative');
        if (negativeTech.length >= 2) {
          supportFactors.push(`技术面: ${negativeTech.map((s: any) => s.signal).join('、')}`);
        }

        // 如果评分仍然较高，提示风险
        if ((analysis.score || 0) > 60) {
          riskFactors.push('技术面仍然偏强，卖出可能过早');
        }
      }

      // 3. 生成建议
      let suggestion = '';
      if (action === 'buy') {
        if (isValid && supportFactors.length >= 2) {
          suggestion = `可以买入，建议分批建仓\n- 首批仓位控制在10%以内\n- 止损位: ¥${(price * 0.95).toFixed(2)} (-5%)`;
        } else if (supportFactors.length >= 1) {
          suggestion = `可以小仓位试探，严格止损\n- 仓位不超过5%\n- 止损位: ¥${(price * 0.97).toFixed(2)} (-3%)`;
        } else {
          suggestion = `建议暂缓买入，等待更好的时机`;
        }
      } else {
        if (isValid && supportFactors.length >= 2) {
          suggestion = `建议卖出，技术面已转弱`;
        } else if (riskFactors.length === 0) {
          suggestion = `可以继续持有，但需密切关注`;
        } else {
          suggestion = `建议减仓，降低风险敞口`;
        }
      }

      // 4. 格式化输出
      const summary = `
交易决策验证 - ${action === 'buy' ? '买入' : '卖出'}${symbol}
=====================================
决策评估: ${isValid ? '✓ 合理' : '⚠ 需谨慎'}
${reason ? `交易理由: ${reason}\n` : ''}
支持因素:
${supportFactors.length > 0
  ? supportFactors.map(f => `✓ ${f}`).join('\n')
  : '- 暂无明显支持因素'}

风险因素:
${riskFactors.length > 0
  ? riskFactors.map(f => `⚠ ${f}`).join('\n')
  : '- 暂无明显风险'}

建议:
${suggestion}

当前价格: ¥${analysis.price.toFixed(2)}
计划价格: ¥${price.toFixed(2)} ${quantity ? `(${quantity}股)` : ''}
`.trim();

      return {
        content: [{ type: "text" as const, text: summary }],
        details: {
          is_valid: isValid,
          support_factors: supportFactors,
          risk_factors: riskFactors,
          suggestion,
          analysis
        }
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `验证失败: ${msg}` }],
        details: undefined
      };
    }
  }
};

// 导出工具数组
export const quantDecisionTools = [
  analyzeStockQuantTool,
  compareStocksQuantTool,
  validateTradeDecisionTool
];
