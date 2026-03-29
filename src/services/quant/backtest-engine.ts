import fs from 'fs/promises';
import path from 'path';
import { BacktestOptions, BacktestResult, Trade, Position, QuantStrategy } from './types';
import { StockDBService, KlineCacheService } from '../stock-db/index.js';
import {
  rollingMean, rsi as calcRsi, macd as calcMacd, bollinger,
  lastNum,
} from '../../infrastructure/data-sources/technical.js';

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

    // 1. 获取股票池（基于 strategy.screening 真实筛选）
    const symbols = await this.getStockPool(strategy);
    if (symbols.length === 0) {
      throw new Error('股票池为空，请先更新股票数据库（manage_stock_db action=update_stocks）');
    }

    // 2. 预加载所有股票的历史 K 线（避免回测中反复请求网络）
    //    klineMap: symbol → 按日期升序排列的 K 线数组
    const klineMap = new Map<string, Array<{ date: string; close: number; open: number; high: number; low: number; volume: number }>>();
    for (const symbol of symbols) {
      const bars = await this.klineCache.getHistory(symbol, start_date, end_date);
      if (bars.length > 0) {
        klineMap.set(symbol, bars);
      }
    }

    // 3. 构建交易日历（取第一只有数据的股票的日期序列）
    const activeSymbols = [...klineMap.keys()];
    if (activeSymbols.length === 0) {
      throw new Error('所有股票均无历史数据，请检查日期范围或先缓存数据');
    }
    const calendar = klineMap.get(activeSymbols[0])!.map(b => b.date);

    // 4. 初始化
    let cash = initial_capital;
    const positions: Map<string, Position> = new Map();
    const trades: Trade[] = [];
    const equityCurve: Array<{ date: string; value: number }> = [];

    // 5. 逐日回测（无前视偏差：信号计算只用截止当日的历史数据）
    for (let dayIdx = 0; dayIdx < calendar.length; dayIdx++) {
      const date = calendar[dayIdx];

      // 先检查持仓的止损止盈（用当日该股票的实际收盘价）
      for (const [symbol, pos] of positions.entries()) {
        const bars = klineMap.get(symbol);
        const bar = bars?.find(b => b.date === date);
        if (!bar) continue;

        const currentPrice = bar.close;
        const pnl_pct = (currentPrice - pos.cost) / pos.cost;

        let shouldSell = false;
        let reason = '';

        if (strategy.exit.stop_loss && pnl_pct <= -strategy.exit.stop_loss) {
          shouldSell = true;
          reason = `止损 ${(pnl_pct * 100).toFixed(2)}%`;
        }
        if (!shouldSell && strategy.exit.take_profit && pnl_pct >= strategy.exit.take_profit) {
          shouldSell = true;
          reason = `止盈 ${(pnl_pct * 100).toFixed(2)}%`;
        }

        if (shouldSell) {
          const proceeds = pos.quantity * currentPrice * (1 - commission);
          cash += proceeds;
          const pnl = proceeds - pos.quantity * pos.cost;
          trades.push({
            date, symbol, name: pos.name, action: 'sell',
            price: currentPrice, quantity: pos.quantity,
            commission: pos.quantity * currentPrice * commission,
            pnl, pnl_pct, reason,
          });
          positions.delete(symbol);
        }
      }

      // 检查每只股票的信号（截止当日的历史切片，无前视偏差）
      for (const symbol of activeSymbols) {
        const bars = klineMap.get(symbol)!;
        // 取截止当日（含）的所有 K 线
        const sliceIdx = bars.findIndex(b => b.date === date);
        if (sliceIdx < 0) continue; // 该股票当日无数据（停牌等）
        const slice = bars.slice(0, sliceIdx + 1);
        const close = slice.map(b => b.close);
        const currentPrice = slice[slice.length - 1].close;

        const hasPosition = positions.has(symbol);
        const signal = this.checkSignalFromClose(close, strategy, hasPosition);

        if (signal === 'buy' && !hasPosition && positions.size < strategy.position.max_stocks) {
          const maxPosition = initial_capital * strategy.position.max_position_pct;
          const quantity = Math.floor(maxPosition / currentPrice / 100) * 100;

          if (quantity > 0 && cash >= quantity * currentPrice * (1 + commission)) {
            const cost = quantity * currentPrice * (1 + commission);
            cash -= cost;
            positions.set(symbol, {
              symbol, name: symbol, quantity,
              cost: cost / quantity, entry_date: date,
            });
            trades.push({
              date, symbol, name: symbol, action: 'buy',
              price: currentPrice, quantity,
              commission: quantity * currentPrice * commission,
              reason: '买入信号触发',
            });
          }
        } else if (signal === 'sell' && hasPosition) {
          const pos = positions.get(symbol)!;
          const proceeds = pos.quantity * currentPrice * (1 - commission);
          cash += proceeds;
          const pnl = proceeds - pos.quantity * pos.cost;
          const pnl_pct = pnl / (pos.quantity * pos.cost);
          trades.push({
            date, symbol, name: pos.name, action: 'sell',
            price: currentPrice, quantity: pos.quantity,
            commission: pos.quantity * currentPrice * commission,
            pnl, pnl_pct, reason: '卖出信号触发',
          });
          positions.delete(symbol);
        }
      }

      // 计算当日权益（各持仓用当日实际收盘价）
      let positionValue = 0;
      for (const [symbol, pos] of positions.entries()) {
        const bars = klineMap.get(symbol);
        const bar = bars?.find(b => b.date === date);
        positionValue += pos.quantity * (bar?.close ?? pos.cost);
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
    const filters = strategy.screening?.filters || {};

    // 优先使用本地数据库筛选（需先执行 manage_stock_db update_stocks）
    const stocks = this.stockDB.filter({
      market: strategy.screening?.market || 'A',
      industry: strategy.screening?.sector,
      min_market_cap: 50,           // 市值 >= 50 亿，过滤微盘
      max_pe: filters.pe_range?.[1],
      min_pe: filters.pe_range?.[0],
      max_pb: filters.pb_range?.[1],
      min_pb: filters.pb_range?.[0],
      exclude_st: true,
      exclude_suspended: true,
      list_days: 365,               // 上市满 1 年
    });

    if (stocks.length === 0) {
      // 区分两种情况：数据库为空 vs 筛选条件过严
      const totalStocks = this.stockDB.filter({ market: strategy.screening?.market || 'A' });
      if (totalStocks.length === 0) {
        throw new Error('股票数据库为空，请先执行 manage_stock_db action=update_stocks 更新数据库');
      }
      // 筛选条件过严，返回空池而不是回退到无关股票
      const filterDesc = [
        strategy.screening?.sector ? `行业=${strategy.screening.sector}` : null,
        filters.pe_range ? `PE=[${filters.pe_range[0] ?? '-'}~${filters.pe_range[1] ?? '-'}]` : null,
        filters.pb_range ? `PB=[${filters.pb_range[0] ?? '-'}~${filters.pb_range[1] ?? '-'}]` : null,
      ].filter(Boolean).join(', ');
      throw new Error(`策略筛选条件过严，无股票满足条件（${filterDesc || '当前筛选器'}），请放宽筛选范围`);
    }

    // 限制最多 50 只，避免回测时间过长
    return stocks.slice(0, 50).map(s => s.symbol);
  }

  /**
   * 基于历史 close 数组计算信号（无前视偏差）
   * @param close 截止当日（含）的收盘价序列，升序
   */
  private checkSignalFromClose(
    close: number[],
    strategy: QuantStrategy,
    hasPosition: boolean,
  ): 'buy' | 'sell' | null {
    if (close.length < 30) return null; // 数据不足，跳过

    // 计算技术指标（只用传入的历史切片）
    const n = close.length;
    const ma5  = lastNum(rollingMean(close, 5)) ?? 0;
    const ma20 = lastNum(rollingMean(close, 20)) ?? 0;
    const ma60 = n >= 60 ? (lastNum(rollingMean(close, 60)) ?? 0) : 0;
    const rsiArr = calcRsi(close, 14);
    const rsiVal = lastNum(rsiArr) ?? 50;
    const { histogram } = calcMacd(close);
    const macdHist = histogram[n - 1] ?? 0;
    const bb = bollinger(close);
    const bbUpper = lastNum(bb.upper) ?? 0;
    const bbLower = lastNum(bb.lower) ?? 0;
    const curPrice = close[n - 1];

    const tech = { rsi: rsiVal, ma5, ma20, ma60, macd_histogram: macdHist, close: curPrice, bollinger_upper: bbUpper, bollinger_lower: bbLower };

    if (hasPosition) {
      if (strategy.exit.conditions?.length) {
        const exitMatch = this.matchConditions(tech, strategy.exit.conditions, 'OR');
        if (exitMatch) return 'sell';
      }
    } else {
      const entryMatch = this.matchConditions(tech, strategy.entry.conditions, strategy.entry.logic);
      if (entryMatch) return 'buy';
    }

    return null;
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
      if (operator === 'golden_cross') return macd > 0;
      if (operator === 'death_cross') return macd < 0;
    }

    if (indicator === 'bollinger') {
      const price = tech.close || 0;
      const upper = tech.bollinger_upper || 0;
      const lower = tech.bollinger_lower || 0;
      if (operator === 'touch_lower') return lower > 0 && price <= lower * 1.01;
      if (operator === 'touch_upper') return upper > 0 && price >= upper * 0.99;
      if (operator === 'break_upper') return upper > 0 && price > upper;
      if (operator === 'break_lower') return lower > 0 && price < lower;
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
