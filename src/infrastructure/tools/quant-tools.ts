/**
 * Quant Tools - 量化分析工具集
 *
 * 提供 6 个量化工具：
 * 1. manage_quant_strategy - 管理量化策略
 * 2. run_backtest - 运行回测
 * 3. generate_signals - 生成交易信号
 * 4. score_stock - 股票因子评分
 * 5. train_signal_model - 训练信号模型
 * 6. combine_strategy_signals - 组合多策略信号
 */

import { Type } from '@sinclair/typebox';
import type { ToolDefinition } from "./index.js";
import { QuantService } from '../../services/quant/quant-service.js';
import { SignalGenerator, StockData } from '../../services/quant/signal-generator.js';
import { FactorLibrary, TechnicalIndicators } from '../../services/quant/factor-library.js';
import { BacktestEngine } from '../../services/quant/backtest-engine.js';
import { PerformanceAnalyzer } from '../../services/quant/performance-analyzer.js';
import { StockDBService } from '../../services/data/stock-db-service.js';
import { get_stock_realtime_price, get_stock_info } from '../../infrastructure/akshare-ts/index.js';
import { callPythonResilient } from './shared/python-caller-resilient-adapter.js';

// 初始化服务
const quantService = new QuantService();
const stockDBService = new StockDBService('.pi-invest');
const factorLibrary = new FactorLibrary(stockDBService);
const signalGenerator = new SignalGenerator('.pi-invest/quant/signals', factorLibrary);
const backtestEngine = new BacktestEngine();
const performanceAnalyzer = new PerformanceAnalyzer('.pi-invest/quant/signals');

/**
 * 辅助函数：计算完整的技术指标
 */
async function calculateAllIndicators(symbol: string): Promise<TechnicalIndicators> {
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

  const volumeRatio = 1.0;
  const atr = 0;

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
    volume_ratio: volumeRatio,
    atr,
    pe: fundamentals.pe,
    pb: fundamentals.pb,
    roe: fundamentals.roe,
    gross_margin: fundamentals.gross_margin,
    debt_ratio: fundamentals.debt_ratio,
  };
}

/**
 * 1. 管理量化策略
 */
export const manageQuantStrategyTool: ToolDefinition = {
  name: 'manage_quant_strategy',
  label: '管理量化策略',
  description: `管理量化策略（创建/列表/启用/禁用/删除）。

使用场景：
- 创建新的量化策略（RSI、MACD、均线等）
- 查看所有策略列表
- 启用/禁用策略
- 删除无效策略

策略示例：
- RSI超卖反转：RSI < 30 买入，RSI > 70 卖出
- 均线金叉：MA5 上穿 MA20 买入
- MACD策略：MACD > 0 且 DIF > DEA 买入`,

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal('create'),
      Type.Literal('list'),
      Type.Literal('enable'),
      Type.Literal('disable'),
      Type.Literal('delete'),
      Type.Literal('get')
    ], {
      description: '操作类型：create=创建, list=列表, enable=启用, disable=禁用, delete=删除, get=获取详情'
    }),
    strategy_id: Type.Optional(Type.String({
      description: '策略ID（enable/disable/delete/get 操作必需）'
    })),
    name: Type.Optional(Type.String({
      description: '策略名称（create 操作必需）'
    })),
    description: Type.Optional(Type.String({
      description: '策略描述（create 操作可选）'
    })),
    entry_conditions: Type.Optional(Type.Array(Type.Object({
      indicator: Type.String({ description: '指标名称，如 rsi, ma5, macd_dif' }),
      operator: Type.String({ description: '操作符：>, <, >=, <=, ==, cross_above, cross_below' }),
      value: Type.Union([Type.Number(), Type.String()], { description: '比较值或另一个指标名' })
    }), {
      description: '入场条件列表（create 操作必需）'
    })),
    entry_logic: Type.Optional(Type.Union([Type.Literal('and'), Type.Literal('or')], {
      description: '条件逻辑：and=全部满足, or=任一满足（默认 and）',
      default: 'and'
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { action, strategy_id, name, description, entry_conditions, entry_logic } = params;

      switch (action) {
        case 'list': {
          const strategies = await quantService.listStrategies();
          const summary = strategies.map(s => ({
            id: s.id,
            name: s.name,
            enabled: s.enabled,
            created_at: s.created_at
          }));
          return {
            content: [{ type: "text" as const, text: JSON.stringify(summary, null, 2) }],
            details: undefined
          };
        }

        case 'get': {
          if (!strategy_id) {
            return {
              content: [{ type: "text" as const, text: 'Error: strategy_id is required for get action' }],
              details: undefined
            };
          }
          const strategy = await quantService.getStrategy(strategy_id);
          if (!strategy) {
            return {
              content: [{ type: "text" as const, text: `Strategy ${strategy_id} not found` }],
              details: undefined
            };
          }
          return {
            content: [{ type: "text" as const, text: JSON.stringify(strategy, null, 2) }],
            details: undefined
          };
        }

        case 'create': {
          if (!name || !entry_conditions) {
            return {
              content: [{ type: "text" as const, text: 'Error: name and entry_conditions are required for create action' }],
              details: undefined
            };
          }
          const strategy = await quantService.createStrategy({
            name,
            description: description || '',
            enabled: true,
            screening: {
              filters: {}
            },
            entry: {
              conditions: entry_conditions,
              logic: (entry_logic || 'and').toUpperCase() as 'AND' | 'OR'
            },
            exit: {
              conditions: []
            },
            position: {
              max_position_pct: 20,
              max_stocks: 10
            }
          });
          return {
            content: [{ type: "text" as const, text: `Strategy created: ${strategy.id}\n${JSON.stringify(strategy, null, 2)}` }],
            details: undefined
          };
        }

        case 'enable': {
          if (!strategy_id) {
            return {
              content: [{ type: "text" as const, text: 'Error: strategy_id is required for enable action' }],
              details: undefined
            };
          }
          const strategy = await quantService.enableStrategy(strategy_id);
          if (!strategy) {
            return {
              content: [{ type: "text" as const, text: `Strategy ${strategy_id} not found` }],
              details: undefined
            };
          }
          return {
            content: [{ type: "text" as const, text: `Strategy ${strategy_id} enabled` }],
            details: undefined
          };
        }

        case 'disable': {
          if (!strategy_id) {
            return {
              content: [{ type: "text" as const, text: 'Error: strategy_id is required for disable action' }],
              details: undefined
            };
          }
          const strategy = await quantService.disableStrategy(strategy_id);
          if (!strategy) {
            return {
              content: [{ type: "text" as const, text: `Strategy ${strategy_id} not found` }],
              details: undefined
            };
          }
          return {
            content: [{ type: "text" as const, text: `Strategy ${strategy_id} disabled` }],
            details: undefined
          };
        }

        case 'delete': {
          if (!strategy_id) {
            return {
              content: [{ type: "text" as const, text: 'Error: strategy_id is required for delete action' }],
              details: undefined
            };
          }
          const success = await quantService.deleteStrategy(strategy_id);
          if (!success) {
            return {
              content: [{ type: "text" as const, text: `Strategy ${strategy_id} not found` }],
              details: undefined
            };
          }
          return {
            content: [{ type: "text" as const, text: `Strategy ${strategy_id} deleted` }],
            details: undefined
          };
        }

        default:
          return {
            content: [{ type: "text" as const, text: `Unknown action: ${action}` }],
            details: undefined
          };
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `Error: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 2. 运行回测
 */
export const runBacktestTool: ToolDefinition = {
  name: 'run_backtest',
  label: '运行回测',
  description: `对量化策略进行历史回测，评估策略表现。

返回指标：
- 总收益率、年化收益率
- 最大回撤
- 胜率、盈亏比
- 夏普比率
- 交易次数、持仓天数

注意：回测需要历史K线数据，确保数据库中有足够的历史数据。`,

  parameters: Type.Object({
    strategy_id: Type.String({
      description: '策略ID（从 manage_quant_strategy 获取）'
    }),
    start_date: Type.String({
      description: '回测开始日期，格式 YYYY-MM-DD'
    }),
    end_date: Type.String({
      description: '回测结束日期，格式 YYYY-MM-DD'
    }),
    symbols: Type.Optional(Type.Array(Type.String(), {
      description: '股票代码列表（可选，不提供则使用全市场）'
    })),
    initial_capital: Type.Optional(Type.Number({
      description: '初始资金（默认 100000）',
      default: 100000
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { strategy_id, start_date, end_date, symbols, initial_capital = 100000 } = params;

      // 获取策略
      const strategy = await quantService.getStrategy(strategy_id);
      if (!strategy) {
        return {
          content: [{ type: "text" as const, text: `Strategy ${strategy_id} not found` }],
          details: undefined
        };
      }

      // 确定股票列表
      let stockList = symbols;
      if (!stockList || stockList.length === 0) {
        // 如果没有指定股票，使用默认列表（A股主要指数成分股）
        stockList = ['000001', '600000', '600036', '601318', '600519']; // 示例：平安、浦发、招行、平安、茅台
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
`;

      return {
        content: [{ type: "text" as const, text: summary }],
        details: result
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `Error: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 3. 生成交易信号
 */
export const generateSignalsTool: ToolDefinition = {
  name: 'generate_signals',
  label: '生成交易信号',
  description: `基于量化策略生成交易信号（买入/卖出）。

使用场景：
- 扫描单只股票，判断是否符合策略条件
- 扫描多只股票，筛选出符合条件的标的
- 获取信号的置信度和原因

返回信息：
- 信号类型（buy/sell）
- 置信度（0-1）
- 触发原因（哪些指标满足条件）
- 当前价格和技术指标`,

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal('scan'),
      Type.Literal('batch')
    ], {
      description: 'scan=扫描单只股票, batch=批量扫描'
    }),
    strategy_id: Type.String({
      description: '策略ID（从 manage_quant_strategy 获取）'
    }),
    symbol: Type.Optional(Type.String({
      description: '股票代码（scan 操作必需）'
    })),
    symbols: Type.Optional(Type.Array(Type.String(), {
      description: '股票代码列表（batch 操作必需）'
    })),
    confidence_threshold: Type.Optional(Type.Number({
      description: '置信度阈值（默认 0.5）',
      default: 0.5
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { action, strategy_id, symbol, symbols, confidence_threshold } = params;

      // 获取策略
      const strategy = await quantService.getStrategy(strategy_id);
      if (!strategy) {
        return {
          content: [{ type: "text" as const, text: `Strategy ${strategy_id} not found` }],
          details: undefined
        };
      }

      if (action === 'scan') {
        if (!symbol) {
          return {
            content: [{ type: "text" as const, text: 'Error: symbol is required for scan action' }],
            details: undefined
          };
        }

        // 获取股票信息和价格
        const infoJson = await get_stock_info(symbol);
        const infoData = JSON.parse(infoJson);
        const priceJson = await get_stock_realtime_price(symbol);
        const priceData = JSON.parse(priceJson);

        if (infoData.error || priceData.error) {
          return {
            content: [{ type: "text" as const, text: `Failed to get stock data for ${symbol}` }],
            details: undefined
          };
        }

        // 计算技术指标
        const tech = await calculateAllIndicators(symbol);

        // 生成信号
        const signal = await signalGenerator.generateSignal(
          symbol,
          infoData.name || symbol,
          strategy,
          tech,
          priceData.price || 0
        );

        if (!signal) {
          return {
            content: [{ type: "text" as const, text: `No signal generated for ${symbol} (strategy conditions not met)` }],
            details: undefined
          };
        }

        return {
          content: [{ type: "text" as const, text: JSON.stringify(signal, null, 2) }],
          details: undefined
        };
      } else if (action === 'batch') {
        if (!symbols || symbols.length === 0) {
          return {
            content: [{ type: "text" as const, text: 'Error: symbols array is required for batch action' }],
            details: undefined
          };
        }

        // 批量获取股票数据
        const stockData: StockData[] = [];
        for (const sym of symbols) {
          try {
            const infoJson = await get_stock_info(sym);
            const infoData = JSON.parse(infoJson);
            const priceJson = await get_stock_realtime_price(sym);
            const priceData = JSON.parse(priceJson);
            const tech = await calculateAllIndicators(sym);

            stockData.push({
              symbol: sym,
              name: infoData.name || sym,
              price: priceData.price || 0,
              tech
            });
          } catch (e) {
            console.warn(`Failed to get data for ${sym}:`, e);
          }
        }

        // 扫描市场
        const signals = await signalGenerator.scanMarket(
          strategy,
          stockData,
          confidence_threshold || 0.5
        );

        return {
          content: [{ type: "text" as const, text: JSON.stringify(signals, null, 2) }],
          details: undefined
        };
      } else {
        return {
          content: [{ type: "text" as const, text: `Unknown action: ${action}` }],
          details: undefined
        };
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `Error: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 4. 股票因子评分
 */
export const scoreStockTool: ToolDefinition = {
  name: 'score_stock',
  label: '股票因子评分',
  description: `对股票进行多因子评分，综合技术面和基本面。

评分维度：
- RSI 评分（超卖/超买）
- 均线评分（趋势强度）
- MACD 评分（动量）
- 成交量评分（资金关注度）
- 布林带评分（波动率）

返回：
- 总分（0-100）
- 技术面分数
- 基本面分数（如有）
- 推荐操作（buy/hold/avoid）
- 各维度详细评分`,

  parameters: Type.Object({
    symbol: Type.String({
      description: '股票代码'
    })
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { symbol } = params;

      // 获取当前价格
      const priceJson = await get_stock_realtime_price(symbol);
      const priceData = JSON.parse(priceJson);

      if (priceData.error) {
        return {
          content: [{ type: "text" as const, text: `Failed to get price for ${symbol}` }],
          details: undefined
        };
      }

      // 计算技术指标
      const tech = await calculateAllIndicators(symbol);

      // 计算评分
      const score = factorLibrary.scoreStock(tech, priceData.price || 0);
      score.symbol = symbol;

      return {
        content: [{ type: "text" as const, text: JSON.stringify(score, null, 2) }],
        details: undefined
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `Error: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 5. 训练信号模型
 */
export const trainSignalModelTool: ToolDefinition = {
  name: 'train_signal_model',
  label: '训练信号模型',
  description: `训练机器学习模型，提升信号置信度预测准确性。

功能：
- 基于历史交易数据训练模型
- 学习哪些技术指标组合更有效
- 提升信号的置信度预测

注意：需要足够的历史交易数据（建议 > 100 条）`,

  parameters: Type.Object({
    strategy_id: Type.String({
      description: '策略ID'
    }),
    min_samples: Type.Optional(Type.Number({
      description: '最小样本数（默认 100）',
      default: 100
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { strategy_id, min_samples = 100 } = params;

      // 调用Python训练函数
      const result = await callPythonResilient(
        'train_signal_model',
        { days: 30, min_samples, timeout: 60000 }
      );

      const parsed = JSON.parse(result);

      if (parsed.error) {
        return {
          content: [{ type: "text" as const, text: `训练失败: ${parsed.error}` }],
          details: parsed
        };
      }

      // 格式化训练结果
      const summary = `
✅ 模型训练完成

📊 训练数据:
- 样本数: ${parsed.samples}
- 正样本: ${parsed.positive_samples}
- 负样本: ${parsed.negative_samples}

📈 模型性能:
- 准确率: ${(parsed.accuracy * 100).toFixed(2)}%
- 模型路径: ${parsed.model_path}

💡 特征重要性:
${parsed.feature_importance?.slice(0, 5).map((imp: number, i: number) =>
  `  ${i + 1}. 特征${i + 1}: ${(imp * 100).toFixed(2)}%`
).join('\n') || '  (无数据)'}
      `.trim();

      return {
        content: [{ type: "text" as const, text: summary }],
        details: parsed
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `训练异常: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 6. 组合多策略信号
 */
export const combineStrategySignalsTool: ToolDefinition = {
  name: 'combine_strategy_signals',
  label: '组合多策略信号',
  description: `组合多个策略的交易信号，支持 OR/AND/VOTE 模式。

使用场景：
- RSI + 均线 + 布林带三个信号投票，提高准确率
- 要求所有策略一致才执行（AND 模式）
- 任一策略触发即执行（OR 模式）

返回：组合后的信号和决策元数据（买入/卖出得分、胜出方向）`,

  promptSnippet: `示例1：组合三个策略信号（VOTE模式）
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross", "bollinger_breakout"],
  mode: "vote",
  weights: {"rsi_reversal": 1.5, "ma_cross": 1.0, "bollinger_breakout": 1.2}
})

示例2：要求所有策略一致（AND模式）
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross"],
  mode: "and"
})`,

  parameters: Type.Object({
    symbol: Type.String({
      description: '股票代码'
    }),
    strategy_ids: Type.Array(Type.String(), {
      description: '策略ID列表，至少2个',
      minItems: 2
    }),
    mode: Type.Optional(Type.Union([
      Type.Literal('vote'),
      Type.Literal('and'),
      Type.Literal('or')
    ], {
      description: '组合模式：vote=加权投票（默认）, and=全部一致, or=任一触发'
    })),
    weights: Type.Optional(Type.Record(Type.String(), Type.Number(), {
      description: '策略权重，如 {"rsi_reversal": 1.5, "ma_cross": 1.0}，默认全部为1.0'
    })),
    confidence_threshold: Type.Optional(Type.Number({
      description: '最低置信度阈值，默认 0.5',
      default: 0.5
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { symbol, strategy_ids, mode = 'vote', weights, confidence_threshold = 0.5 } = params;

      if (!strategy_ids || strategy_ids.length < 2) {
        return {
          content: [{ type: "text" as const, text: 'Error: At least 2 strategy_ids required' }],
          details: undefined
        };
      }

      const infoJson = await get_stock_info(symbol);
      const infoData = JSON.parse(infoJson);
      const priceJson = await get_stock_realtime_price(symbol);
      const priceData = JSON.parse(priceJson);

      if (infoData.error || priceData.error) {
        return {
          content: [{ type: "text" as const, text: `Failed to get stock data for ${symbol}` }],
          details: undefined
        };
      }

      const tech = await calculateAllIndicators(symbol);

      const signals: any[] = [];
      for (const strategy_id of strategy_ids) {
        const strategy = await quantService.getStrategy(strategy_id);
        if (!strategy) {
          console.warn(`Strategy ${strategy_id} not found, skipping`);
          continue;
        }

        const signal = await signalGenerator.generateSignal(
          symbol,
          infoData.name || symbol,
          strategy,
          tech,
          priceData.price || 0
        );

        if (signal) {
          signals.push(signal);
        }
      }

      if (signals.length === 0) {
        return {
          content: [{ type: "text" as const, text: `No signals generated for ${symbol}` }],
          details: undefined
        };
      }

      if (signals.length === 1) {
        return {
          content: [{ type: "text" as const, text: JSON.stringify({
            signal: signals[0],
            metadata: { reason: 'insufficient_signals' }
          }, null, 2) }],
          details: undefined
        };
      }

      const { signals: combinedSignals, metadata } = await signalGenerator.combineSignals(
        signals,
        mode,
        weights,
        confidence_threshold
      );

      const result = {
        symbol,
        combined_signals: combinedSignals,
        metadata: {
          mode,
          total_strategies: strategy_ids.length,
          signals_generated: signals.length,
          ...metadata
        }
      };

      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
        details: result
      };

    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `Error: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 工具 7: 策略表现统计
 */
export const getStrategyPerformanceTool: ToolDefinition = {
  name: "get_strategy_performance",
  label: "策略表现统计",
  description: "统计策略的历史信号表现，包括信号数量、胜率、平均收益等",
  parameters: Type.Object({
    strategy_id: Type.String({ description: "策略ID" }),
    days: Type.Optional(Type.Number({ description: "统计最近N天", default: 30 }))
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const strategy = await quantService.getStrategy(params.strategy_id);
      if (!strategy) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({ error: `Strategy ${params.strategy_id} not found` }, null, 2)
          }],
          details: undefined
        };
      }

      // 使用PerformanceAnalyzer分析策略表现
      const metrics = await performanceAnalyzer.analyzeStrategy(
        params.strategy_id,
        strategy.name,
        params.days || 30
      );

      return {
        content: [{ type: "text" as const, text: JSON.stringify(metrics, null, 2) }],
        details: undefined
      };
    } catch (error: any) {
      return {
        content: [{ type: "text" as const, text: JSON.stringify({ error: error.message }, null, 2) }],
        details: undefined
      };
    }
  }
};

/**
 * 导出所有量化工具
 */
export const quantTools: ToolDefinition[] = [
  manageQuantStrategyTool,
  runBacktestTool,
  generateSignalsTool,
  scoreStockTool,
  trainSignalModelTool,
  combineStrategySignalsTool,
  getStrategyPerformanceTool
];
