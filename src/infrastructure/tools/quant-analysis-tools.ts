/**
 * Quant Analysis Tools - 量化基础分析工具集
 *
 * 提供基础的量化分析工具，可单独使用或组合使用
 */

import { Type } from '@sinclair/typebox';
import type { ToolDefinition } from "./index.js";
import { QuantService } from '../../services/quant/quant-service.js';
import { SignalGenerator } from '../../services/quant/signal-generator.js';
import { FactorLibrary } from '../../services/quant/factor-library.js';
import { BacktestEngine } from '../../services/quant/backtest-engine.js';
import { StockDBService } from '../../services/data/stock-db-service.js';
import { queryAndFormatExperience } from '../../services/intelligence/experience-query.js';
import { get_stock_realtime_price, get_stock_info } from '../akshare-ts/index.js';

// 初始化服务
const quantService = new QuantService();
const stockDBService = new StockDBService('.pi-invest/stock.db');
const factorLibrary = new FactorLibrary(stockDBService);
const signalGenerator = new SignalGenerator('.pi-invest/quant/signals', factorLibrary);
const backtestEngine = new BacktestEngine();

/**
 * 1. get_technical_signals - 获取技术信号
 */
export const getTechnicalSignalsTool: ToolDefinition = {
  name: 'get_technical_signals',
  label: '获取技术信号',
  description: `获取单只股票的技术指标信号。

包含指标：
- RSI（相对强弱指标）
- MACD（指数平滑异同移动平均线）
- 均线系统（MA5/10/20/60）
- 布林带

适用场景：
- 快速查看技术面
- 技术分析参考`,

  promptSnippet: '需要获取技术指标信号时',
  promptGuidelines: [
    '返回MACD、RSI、布林带等技术指标',
    '包含买入/卖出信号和强度',
    '可用于短期交易决策'
  ],

  parameters: Type.Object({
    symbol: Type.String({
      description: '股票代码，如 600036.SH'
    })
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { symbol } = params;

      // 获取股票信息和价格
      const [stockInfoStr, priceDataStr] = await Promise.all([
        get_stock_info(symbol),
        get_stock_realtime_price(symbol)
      ]);

      const stockInfo = JSON.parse(stockInfoStr);
      const priceData = JSON.parse(priceDataStr);
      const stockName = stockInfo?.name || symbol;
      const currentPrice = priceData?.current || 0;

      // 计算技术指标
      const [rsi, ma5, ma10, ma20, ma60, macd, bb] = await Promise.all([
        factorLibrary.calculateRSIForSymbol(symbol, 14),
        factorLibrary.calculateMAForSymbol(symbol, 5),
        factorLibrary.calculateMAForSymbol(symbol, 10),
        factorLibrary.calculateMAForSymbol(symbol, 20),
        factorLibrary.calculateMAForSymbol(symbol, 60),
        factorLibrary.calculateMACDForSymbol(symbol),
        factorLibrary.calculateBollingerBands(symbol, 20, 2)
      ]);

      // 生成信号描述
      const signals = [];

      // RSI信号
      if (rsi < 30) {
        signals.push(`✓ RSI超卖(${rsi.toFixed(1)}) - 反弹机会`);
      } else if (rsi > 70) {
        signals.push(`✗ RSI超买(${rsi.toFixed(1)}) - 回调风险`);
      } else {
        signals.push(`○ RSI中性(${rsi.toFixed(1)})`);
      }

      // MACD信号
      if (macd.dif > macd.dea && macd.macd > 0) {
        signals.push(`✓ MACD金叉 - 趋势转多`);
      } else if (macd.dif < macd.dea && macd.macd < 0) {
        signals.push(`✗ MACD死叉 - 趋势转空`);
      } else {
        signals.push(`○ MACD中性`);
      }

      // 均线信号
      if (ma5 > ma10 && ma10 > ma20) {
        signals.push(`✓ 均线多头排列 - 短中期向上`);
      } else if (ma5 < ma10 && ma10 < ma20) {
        signals.push(`✗ 均线空头排列 - 短中期向下`);
      } else {
        signals.push(`○ 均线交织 - 方向不明`);
      }

      // 布林带信号
      if (currentPrice < bb.lower) {
        signals.push(`✓ 跌破布林下轨 - 超卖反弹`);
      } else if (currentPrice > bb.upper) {
        signals.push(`✗ 突破布林上轨 - 超买回调`);
      } else {
        signals.push(`○ 布林带中轨运行`);
      }

      const summary = `
${stockName}(${symbol}) 技术信号
=====================================
当前价格: ¥${currentPrice.toFixed(2)}

技术指标:
${signals.join('\n')}

详细数据:
- RSI(14): ${rsi.toFixed(2)}
- MACD: DIF=${macd.dif.toFixed(2)}, DEA=${macd.dea.toFixed(2)}, MACD=${macd.macd.toFixed(2)}
- 均线: MA5=${ma5.toFixed(2)}, MA10=${ma10.toFixed(2)}, MA20=${ma20.toFixed(2)}, MA60=${ma60.toFixed(2)}
- 布林带: 上轨=${bb.upper.toFixed(2)}, 中轨=${bb.middle.toFixed(2)}, 下轨=${bb.lower.toFixed(2)}
`.trim();

      return {
        content: [{ type: "text" as const, text: summary }],
        details: {
          price: currentPrice,
          rsi,
          macd: { dif: macd.dif, dea: macd.dea, histogram: macd.macd },
          ma: { ma5, ma10, ma20, ma60 },
          bollinger: { upper: bb.upper, middle: bb.middle, lower: bb.lower }
        }
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `获取技术信号失败: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 2. get_quant_score - 获取量化评分
 */
export const getQuantScoreTool: ToolDefinition = {
  name: 'get_quant_score',
  label: '获取量化评分',
  description: `获取单只股票的多因子量化评分。

评分维度：
- RSI因子（0-25分）
- MACD因子（0-20分）
- 均线因子（0-20分）
- 布林带因子（0-15分）
- 成交量因子（0-20分）

总分100分，>=60分为偏多，<=40分为偏空`,

  parameters: Type.Object({
    symbol: Type.String({
      description: '股票代码'
    })
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { symbol } = params;

      // 获取股票信息和价格
      const [stockInfoStr, priceDataStr] = await Promise.all([
        get_stock_info(symbol),
        get_stock_realtime_price(symbol)
      ]);

      const stockInfo = JSON.parse(stockInfoStr);
      const priceData = JSON.parse(priceDataStr);
      const stockName = stockInfo?.name || symbol;
      const currentPrice = priceData?.current || 0;

      // 计算技术指标
      const [rsi, ma5, ma10, ma20, macd, bb] = await Promise.all([
        factorLibrary.calculateRSIForSymbol(symbol, 14),
        factorLibrary.calculateMAForSymbol(symbol, 5),
        factorLibrary.calculateMAForSymbol(symbol, 10),
        factorLibrary.calculateMAForSymbol(symbol, 20),
        factorLibrary.calculateMACDForSymbol(symbol),
        factorLibrary.calculateBollingerBands(symbol, 20, 2)
      ]);

      // 计算各因子得分
      let rsiScore = 0;
      if (rsi < 30) rsiScore = 25;
      else if (rsi < 40) rsiScore = 20;
      else if (rsi < 50) rsiScore = 15;
      else if (rsi < 60) rsiScore = 10;
      else if (rsi < 70) rsiScore = 5;
      else rsiScore = 0;

      let macdScore = 0;
      if (macd.dif > macd.dea && macd.macd > 0) macdScore = 20;
      else if (macd.dif > macd.dea) macdScore = 15;
      else if (macd.macd > 0) macdScore = 10;
      else macdScore = 5;

      let maScore = 0;
      if (ma5 > ma10 && ma10 > ma20) maScore = 20;
      else if (ma5 > ma10) maScore = 15;
      else if (ma5 > ma20) maScore = 10;
      else maScore = 5;

      let bbScore = 0;
      if (currentPrice < bb.lower) bbScore = 15;
      else if (currentPrice < bb.middle) bbScore = 10;
      else if (currentPrice < bb.upper) bbScore = 5;
      else bbScore = 0;

      const volumeScore = 10; // 简化处理

      const totalScore = rsiScore + macdScore + maScore + bbScore + volumeScore;

      // 评级
      let rating = '';
      if (totalScore >= 75) rating = '强烈看多';
      else if (totalScore >= 60) rating = '偏多';
      else if (totalScore >= 40) rating = '中性';
      else if (totalScore >= 25) rating = '偏空';
      else rating = '强烈看空';

      const summary = `
${stockName}(${symbol}) 量化评分
=====================================
综合评分: ${totalScore}/100 (${rating})

因子得分明细:
- RSI因子: ${rsiScore}/25 ${rsi < 30 ? '(超卖)' : rsi > 70 ? '(超买)' : ''}
- MACD因子: ${macdScore}/20 ${macd.dif > macd.dea ? '(金叉)' : '(死叉)'}
- 均线因子: ${maScore}/20 ${ma5 > ma10 && ma10 > ma20 ? '(多头)' : '(空头)'}
- 布林带因子: ${bbScore}/15 ${currentPrice < bb.lower ? '(超卖)' : currentPrice > bb.upper ? '(超买)' : ''}
- 成交量因子: ${volumeScore}/20

技术面总结: ${rating}，${totalScore >= 60 ? 'RSI超卖反弹概率高' : totalScore >= 40 ? '观察等待更明确信号' : '技术面偏弱'}
`.trim();

      return {
        content: [{ type: "text" as const, text: summary }],
        details: {
          total_score: totalScore,
          rating,
          factor_scores: {
            rsi: rsiScore,
            macd: macdScore,
            ma: maScore,
            bollinger: bbScore,
            volume: volumeScore
          },
          indicators: { rsi, macd, ma5, ma10, ma20, bollinger: bb }
        }
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `获取量化评分失败: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 3. query_similar_cases - 查询历史案例
 */
export const querySimilarCasesTool: ToolDefinition = {
  name: 'query_similar_cases',
  label: '查询历史案例',
  description: `查询类似场景的历史经验和案例。

查询维度：
- 技术形态（RSI超卖、MACD金叉等）
- 股票特征（板块、市值等）
- 历史胜率和收益

返回内容：
- 历史案例数量
- 胜率统计
- 平均收益
- 操作建议`,

  parameters: Type.Object({
    scenario: Type.String({
      description: '场景描述，如 "RSI超卖"、"MACD金叉"、"均线金叉"'
    }),
    symbol: Type.Optional(Type.String({
      description: '股票代码（可选），用于精确匹配'
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { scenario, symbol } = params;

      // 调用经验查询服务
      const result = queryAndFormatExperience({ scenario, symbol });

      return {
        content: [{ type: "text" as const, text: result }],
        details: undefined
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `查询历史案例失败: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 4. backtest_strategy - 策略回测
 */
export const backtestStrategyTool: ToolDefinition = {
  name: 'backtest_strategy',
  label: '策略回测',
  description: `对量化策略进行历史回测，评估策略表现。

回测指标：
- 总收益率、年化收益率
- 最大回撤
- 夏普比率
- 胜率、盈亏比
- 交易次数、持仓天数

适用场景：
- 验证策略有效性
- 优化策略参数
- 评估风险收益比`,

  promptSnippet: '需要回测交易策略时',
  promptGuidelines: [
    '用于验证策略的历史表现',
    '返回收益率、夏普比率、最大回撤等指标',
    '回测时间较长，建议使用 task_create 创建后台任务'
  ],

  parameters: Type.Object({
    strategy_id: Type.String({
      description: '策略ID'
    }),
    start_date: Type.String({
      description: '回测开始日期，格式 YYYY-MM-DD'
    }),
    end_date: Type.String({
      description: '回测结束日期，格式 YYYY-MM-DD'
    }),
    symbols: Type.Optional(Type.Array(Type.String(), {
      description: '股票代码列表（可选），默认使用主要指数成分股'
    })),
    initial_capital: Type.Optional(Type.Number({
      description: '初始资金（可选），默认100000'
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { strategy_id, start_date, end_date, symbols, initial_capital = 100000 } = params;

      // 获取策略
      const strategy = await quantService.getStrategy(strategy_id);
      if (!strategy) {
        return {
          content: [{ type: "text" as const, text: `策略 ${strategy_id} 不存在` }],
          details: undefined
        };
      }

      // 确定股票列表
      let stockList = symbols;
      if (!stockList || stockList.length === 0) {
        stockList = ['000001', '600000', '600036', '601318', '600519'];
      }

      // 运行回测
      const result = await backtestEngine.runBacktest(
        strategy,
        start_date,
        end_date,
        stockList,
        initial_capital
      );

      // 格式化输出
      const summary = `
回测结果 - ${strategy.name}
=====================================
时间范围: ${result.start_date} 至 ${result.end_date}
初始资金: ¥${result.initial_capital.toLocaleString()}
最终资金: ¥${result.final_capital.toLocaleString()}

收益指标:
- 总收益率: ${result.total_return.toFixed(2)}%
- 年化收益率: ${result.annual_return.toFixed(2)}%
- 最大回撤: ${result.max_drawdown.toFixed(2)}%

交易指标:
- 总交易次数: ${result.total_trades}
- 盈利交易: ${result.winning_trades} (胜率: ${result.win_rate.toFixed(2)}%)
- 亏损交易: ${result.losing_trades}
- 盈亏比: ${result.profit_loss_ratio.toFixed(2)}

风险指标:
- 夏普比率: ${result.sharpe_ratio.toFixed(2)}
- 波动率: ${result.volatility.toFixed(2)}%

持仓指标:
- 平均持仓天数: ${result.avg_holding_days.toFixed(1)}天
- 最大同时持仓数: ${result.max_position_count}

交易记录 (前10笔):
${result.trades.slice(0, 10).map(t =>
  `${t.symbol} | ${t.entry_date} → ${t.exit_date} | ${t.profit > 0 ? '+' : ''}${t.profit_pct.toFixed(2)}% | ${t.exit_reason}`
).join('\n')}
${result.trades.length > 10 ? `\n... 共 ${result.trades.length} 笔交易` : ''}
`.trim();

      return {
        content: [{ type: "text" as const, text: summary }],
        details: result
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `回测失败: ${msg}` }],
        details: undefined
      };
    }
  }
};

// 导出工具数组
export const quantAnalysisTools = [
  getTechnicalSignalsTool,
  getQuantScoreTool,
  querySimilarCasesTool,
  backtestStrategyTool
];
