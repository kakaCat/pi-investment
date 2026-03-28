import fs from 'fs/promises';
import path from 'path';
import { BacktestOptions, BacktestResult, Trade, Position, QuantStrategy } from './types';
import { StockDBService, KlineCacheService } from '../stock-db/index.js';

export class BacktestEngine {
  private backtestsDir = '.pi-invest/quant/backtests';
  private stockDB: StockDBService;
  private klineCache: KlineCacheService;

  constructor() {
    this.stockDB = new StockDBService('.pi-invest');
    this.klineCache = new KlineCacheService(this.stockDB);
  }

  async run(strategy: QuantStrategy, options: Omit<BacktestOptions, 'strategy_id'>): Promise<BacktestResult> {
    const { start_date, end_date, initial_capital, commission } = options;

    // 1. 获取股票池（简化版：只测试单只股票或小池子）
    const symbols = await this.getStockPool(strategy);

    // 2. 初始化
    let cash = initial_capital;
    const positions: Map<string, Position> = new Map();
    const trades: Trade[] = [];
    const equityCurve: Array<{ date: string; value: number }> = [];

    // 3. 获取交易日历（使用缓存）
    if (symbols.length === 0) {
      throw new Error('股票池为空');
    }

    const historyData = await this.klineCache.getHistory(symbols[0], start_date, end_date);
    const calendar = historyData || [];

    // 4. 逐日回测
    for (const day of calendar) {
      const date = day.date;

      // 先检查持仓的止损止盈
      for (const [symbol, pos] of positions.entries()) {
        const currentPrice = day.close;
        const pnl_pct = (currentPrice - pos.cost) / pos.cost;

        let shouldSell = false;
        let reason = '';

        // 止损检查
        if (strategy.exit.stop_loss && pnl_pct <= -strategy.exit.stop_loss) {
          shouldSell = true;
          reason = `止损 ${(pnl_pct * 100).toFixed(2)}%`;
        }

        // 止盈检查
        if (strategy.exit.take_profit && pnl_pct >= strategy.exit.take_profit) {
          shouldSell = true;
          reason = `止盈 ${(pnl_pct * 100).toFixed(2)}%`;
        }

        if (shouldSell) {
          const proceeds = pos.quantity * currentPrice * (1 - commission);
          cash += proceeds;
          const pnl = proceeds - pos.quantity * pos.cost;

          trades.push({
            date,
            symbol,
            name: symbol,
            action: 'sell',
            price: currentPrice,
            quantity: pos.quantity,
            commission: pos.quantity * currentPrice * commission,
            pnl,
            pnl_pct,
            reason,
          });
          positions.delete(symbol);
        }
      }

      // 检查每只股票的信号
      for (const symbol of symbols) {
        const signal = await this.checkSignal(symbol, date, strategy, positions.has(symbol));

        if (signal === 'buy' && !positions.has(symbol) && positions.size < strategy.position.max_stocks) {
          // 买入
          const price = day.close;
          const maxPosition = initial_capital * strategy.position.max_position_pct;
          const quantity = Math.floor(maxPosition / price / 100) * 100; // A股100股整数倍

          if (quantity > 0 && cash >= quantity * price * (1 + commission)) {
            const cost = quantity * price * (1 + commission);
            cash -= cost;
            positions.set(symbol, {
              symbol,
              name: symbol,
              quantity,
              cost: cost / quantity,
              entry_date: date,
            });
            trades.push({
              date,
              symbol,
              name: symbol,
              action: 'buy',
              price,
              quantity,
              commission: quantity * price * commission,
              reason: '买入信号触发',
            });
          }
        } else if (signal === 'sell' && positions.has(symbol)) {
          // 卖出（技术指标信号）
          const pos = positions.get(symbol)!;
          const price = day.close;
          const proceeds = pos.quantity * price * (1 - commission);
          cash += proceeds;

          const pnl = proceeds - pos.quantity * pos.cost;
          const pnl_pct = pnl / (pos.quantity * pos.cost);

          trades.push({
            date,
            symbol,
            name: symbol,
            action: 'sell',
            price,
            quantity: pos.quantity,
            commission: pos.quantity * price * commission,
            pnl,
            pnl_pct,
            reason: '卖出信号触发',
          });
          positions.delete(symbol);
        }
      }

      // 计算当日权益
      let positionValue = 0;
      for (const pos of positions.values()) {
        positionValue += pos.quantity * day.close;
      }
      equityCurve.push({ date, value: cash + positionValue });
    }

    // 5. 计算绩效
    const performance = this.calculatePerformance(equityCurve, trades, initial_capital);

    const result: BacktestResult = {
      id: `backtest_${Date.now()}`,
      strategy_id: strategy.id,
      period: { start: start_date, end: end_date },
      performance,
      trades,
      equity_curve: equityCurve,
      created_at: new Date().toISOString(),
    };

    // 6. 保存结果
    await fs.mkdir(this.backtestsDir, { recursive: true });
    await fs.writeFile(
      path.join(this.backtestsDir, `${result.id}.json`),
      JSON.stringify(result, null, 2)
    );

    return result;
  }

  private async getStockPool(strategy: QuantStrategy): Promise<string[]> {
    // 简化版：返回一些常见的大盘股作为测试池
    // TODO: 根据 strategy.screening 实现真实筛选
    const testPool = [
      '000001', // 平安银行
      '600036', // 招商银行
      '601318', // 中国平安
      '600519', // 贵州茅台
      '000858', // 五粮液
    ];

    // 如果指定了行业，可以进一步过滤
    if (strategy.screening.sector) {
      // TODO: 调用 get_sector_list 获取行业股票
      return testPool.slice(0, 2);
    }

    return testPool;
  }

  private async checkSignal(
    symbol: string,
    date: string,
    strategy: QuantStrategy,
    hasPosition: boolean
  ): Promise<'buy' | 'sell' | null> {
    try {
      // 获取技术指标
      const techJson = await TS_FUNCTIONS['calculate_technical_indicators']({
        symbol,
        indicators: ['ma', 'rsi', 'macd']
      });
      const tech = JSON.parse(techJson);

      // 检查卖出信号（持仓时）
      if (hasPosition) {
        // 止损止盈检查在主循环中处理
        if (strategy.exit.conditions) {
          const exitMatch = this.matchConditions(tech, strategy.exit.conditions, 'OR');
          if (exitMatch) return 'sell';
        }
      }

      // 检查买入信号（无持仓时）
      if (!hasPosition) {
        const entryMatch = this.matchConditions(tech, strategy.entry.conditions, strategy.entry.logic);
        if (entryMatch) return 'buy';
      }

      return null;
    } catch {
      return null;
    }
  }

  private matchConditions(tech: any, conditions: any[], logic: 'AND' | 'OR'): boolean {
    const results = conditions.map(c => this.matchCondition(tech, c));
    return logic === 'AND' ? results.every(r => r) : results.some(r => r);
  }

  private matchCondition(tech: any, condition: any): boolean {
    const { indicator, operator, value } = condition;

    if (indicator === 'rsi') {
      const rsi = tech.rsi || 50;
      if (operator === '<') return rsi < value;
      if (operator === '>') return rsi > value;
      if (operator === '<=') return rsi <= value;
      if (operator === '>=') return rsi >= value;
    }

    if (indicator === 'ma_cross') {
      const ma5 = tech.ma5 || 0;
      const ma20 = tech.ma20 || 0;
      if (operator === 'cross_above') return ma5 > ma20;
      if (operator === 'cross_below') return ma5 < ma20;
    }

    if (indicator === 'macd') {
      const macd = tech.macd_histogram || 0;
      if (operator === '>') return macd > value;
      if (operator === '<') return macd < value;
    }

    return false;
  }

  private calculatePerformance(
    equityCurve: Array<{ date: string; value: number }>,
    trades: Trade[],
    initialCapital: number
  ) {
    if (equityCurve.length === 0) {
      return {
        total_return: 0,
        annual_return: 0,
        sharpe_ratio: 0,
        max_drawdown: 0,
        win_rate: 0,
        profit_factor: 0,
        total_trades: 0,
      };
    }

    const finalValue = equityCurve[equityCurve.length - 1].value;
    const totalReturn = (finalValue - initialCapital) / initialCapital;

    // 计算年化收益
    const days = equityCurve.length;
    const years = days / 252; // 交易日
    const annualReturn = years > 0 ? Math.pow(1 + totalReturn, 1 / years) - 1 : totalReturn;

    // 计算最大回撤
    let maxDrawdown = 0;
    let peak = equityCurve[0].value;
    for (const point of equityCurve) {
      if (point.value > peak) {
        peak = point.value;
      }
      const drawdown = (peak - point.value) / peak;
      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown;
      }
    }

    // 计算夏普比率（简化版，假设无风险利率为3%）
    const returns = [];
    for (let i = 1; i < equityCurve.length; i++) {
      const dailyReturn = (equityCurve[i].value - equityCurve[i - 1].value) / equityCurve[i - 1].value;
      returns.push(dailyReturn);
    }
    const avgReturn = returns.reduce((sum, r) => sum + r, 0) / returns.length;
    const stdDev = Math.sqrt(
      returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length
    );
    const riskFreeRate = 0.03 / 252; // 日化无风险利率
    const sharpeRatio = stdDev > 0 ? ((avgReturn - riskFreeRate) / stdDev) * Math.sqrt(252) : 0;

    // 计算胜率和盈亏比
    const sellTrades = trades.filter(t => t.action === 'sell');
    const winTrades = sellTrades.filter(t => (t.pnl || 0) > 0);
    const lossTrades = sellTrades.filter(t => (t.pnl || 0) < 0);
    const winRate = sellTrades.length > 0 ? winTrades.length / sellTrades.length : 0;

    const totalProfit = winTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
    const totalLoss = Math.abs(lossTrades.reduce((sum, t) => sum + (t.pnl || 0), 0));
    const profitFactor = totalLoss > 0 ? totalProfit / totalLoss : totalProfit > 0 ? 999 : 0;

    return {
      total_return: totalReturn,
      annual_return: annualReturn,
      sharpe_ratio: sharpeRatio,
      max_drawdown: maxDrawdown,
      win_rate: winRate,
      profit_factor: profitFactor,
      total_trades: sellTrades.length,
    };
  }
}
