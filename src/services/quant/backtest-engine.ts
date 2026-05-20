import { QuantStrategy } from './types.js';
import { SignalGenerator } from './signal-generator.js';
import { FactorLibrary } from './factor-library.js';
import { StockDBService } from '../data/stock-db-service.js';

/**
 * 回测结果
 */
export interface BacktestResult {
  // 基本信息
  strategy_id: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_capital: number;

  // 收益指标
  total_return: number;        // 总收益率
  annual_return: number;        // 年化收益率
  max_drawdown: number;         // 最大回撤

  // 交易指标
  total_trades: number;         // 总交易次数
  winning_trades: number;       // 盈利交易次数
  losing_trades: number;        // 亏损交易次数
  win_rate: number;             // 胜率
  profit_loss_ratio: number;    // 盈亏比

  // 风险指标
  sharpe_ratio: number;         // 夏普比率
  volatility: number;           // 波动率

  // 持仓指标
  avg_holding_days: number;     // 平均持仓天数
  max_position_count: number;   // 最大同时持仓数

  // 详细记录
  trades: Trade[];              // 交易记录
  daily_equity: DailyEquity[];  // 每日权益曲线
}

/**
 * 交易记录
 */
export interface Trade {
  symbol: string;
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  shares: number;
  profit: number;
  profit_pct: number;
  holding_days: number;
  entry_reason: string;
  exit_reason: string;
}

/**
 * 每日权益
 */
export interface DailyEquity {
  date: string;
  cash: number;
  position_value: number;
  total_equity: number;
  return_pct: number;
  drawdown: number;
}

/**
 * 持仓信息
 */
interface Position {
  symbol: string;
  entry_date: string;
  entry_price: number;
  shares: number;
  entry_reason: string;
}

/**
 * 回测引擎
 */
export class BacktestEngine {
  private signalGenerator: SignalGenerator;
  private factorLibrary: FactorLibrary;

  private readonly COMMISSION_RATE = 0.0003; // A股佣金 0.03%
  private readonly STAMP_TAX_RATE = 0.001;  // 卖出印花税 0.1%

  constructor(stockDBService?: StockDBService) {
    const db = stockDBService || StockDBService.getInstance('.pi-invest');
    this.factorLibrary = new FactorLibrary(db);
    this.signalGenerator = new SignalGenerator('.pi-invest/quant/signals', this.factorLibrary, false);
  }

  /**
   * 运行回测
   */
  async runBacktest(
    strategy: QuantStrategy,
    startDate: string,
    endDate: string,
    symbols: string[],
    initialCapital: number = 100000
  ): Promise<BacktestResult> {
    // 初始化状态
    let cash = initialCapital;
    const positions: Map<string, Position> = new Map();
    const trades: Trade[] = [];
    const dailyEquity: DailyEquity[] = [];

    // 获取交易日列表
    const tradingDays = await this.getTradingDays(startDate, endDate);

    // 逐日模拟
    for (const date of tradingDays) {
      // 获取当日所有股票的价格和指标
      const stockData = await this.getStockDataForDate(symbols, date);

      // 检查持仓，生成卖出信号
      for (const [symbol, position] of positions.entries()) {
        const data = stockData.get(symbol);
        if (!data) continue;

        const signal = await this.signalGenerator.generateSignal(
          symbol,
          data.name,
          strategy,
          data.indicators,
          data.price
        );

        // 卖出条件：1) 策略生成卖出信号 2) 止损/止盈
        if (signal && (signal.action === 'sell' || this.shouldExit(position, data.price, strategy))) {
          const exitReason = signal.action === 'sell'
            ? signal.reason
            : this.getExitReason(position, data.price, strategy);

          // 执行卖出
          const sellValue = position.shares * data.price;
          const sellCommission = sellValue * this.COMMISSION_RATE;
          const stampTax = sellValue * this.STAMP_TAX_RATE;
          cash += (sellValue - sellCommission - stampTax);

          // 记录交易
          const holdingDays = this.calculateDays(position.entry_date, date);
          const profit = sellValue - (position.shares * position.entry_price) - sellCommission - stampTax;
          const profitPct = (profit / (position.shares * position.entry_price)) * 100;

          trades.push({
            symbol,
            entry_date: position.entry_date,
            entry_price: position.entry_price,
            exit_date: date,
            exit_price: data.price,
            shares: position.shares,
            profit,
            profit_pct: profitPct,
            holding_days: holdingDays,
            entry_reason: position.entry_reason,
            exit_reason: exitReason
          });

          positions.delete(symbol);
        }
      }

      // 检查新的买入机会
      if (positions.size < (strategy.position.max_stocks || 10)) {
        for (const [symbol, data] of stockData.entries()) {
          // 跳过已持仓的股票
          if (positions.has(symbol)) continue;

          const signal = await this.signalGenerator.generateSignal(
            symbol,
            data.name,
            strategy,
            data.indicators,
            data.price
          );

          // 买入条件
          if (signal && signal.action === 'buy' && signal.confidence >= 0.6) {
            // 计算买入数量
            const positionSize = this.calculatePositionSize(
              cash,
              data.price,
              strategy,
              positions.size
            );

            if (positionSize > 0 && cash >= positionSize * data.price) {
              // 执行买入
              const shares = Math.floor(positionSize);
              const cost = shares * data.price;
              const buyCommission = Math.max(cost * this.COMMISSION_RATE, 5);
              cash -= (cost + buyCommission);

              positions.set(symbol, {
                symbol,
                entry_date: date,
                entry_price: data.price,
                shares,
                entry_reason: signal.reason
              });
            }
          }
        }
      }

      // 记录每日权益
      const positionValue = this.calculatePositionValue(positions, stockData);
      const totalEquity = cash + positionValue;
      const returnPct = ((totalEquity - initialCapital) / initialCapital) * 100;
      const drawdown = this.calculateDrawdown(dailyEquity, totalEquity);

      dailyEquity.push({
        date,
        cash,
        position_value: positionValue,
        total_equity: totalEquity,
        return_pct: returnPct,
        drawdown
      });
    }

    // 清算所有持仓
    const lastDate = tradingDays[tradingDays.length - 1];
    const lastStockData = await this.getStockDataForDate(symbols, lastDate);

    for (const [symbol, position] of positions.entries()) {
      const data = lastStockData.get(symbol);
      if (!data) continue;

      const sellValue = position.shares * data.price;
      const sellCommission = sellValue * this.COMMISSION_RATE;
      const stampTax = sellValue * this.STAMP_TAX_RATE;
      cash += (sellValue - sellCommission - stampTax);

      const holdingDays = this.calculateDays(position.entry_date, lastDate);
      const profit = sellValue - (position.shares * position.entry_price) - sellCommission - stampTax;
      const profitPct = (profit / (position.shares * position.entry_price)) * 100;

      trades.push({
        symbol,
        entry_date: position.entry_date,
        entry_price: position.entry_price,
        exit_date: lastDate,
        exit_price: data.price,
        shares: position.shares,
        profit,
        profit_pct: profitPct,
        holding_days: holdingDays,
        entry_reason: position.entry_reason,
        exit_reason: '回测结束清仓'
      });
    }

    positions.clear();

    // 计算性能指标
    const finalCapital = cash;
    const totalReturn = ((finalCapital - initialCapital) / initialCapital) * 100;
    const years = this.calculateYears(startDate, endDate);
    const annualReturn = (Math.pow(finalCapital / initialCapital, 1 / years) - 1) * 100;
    const maxDrawdown = this.calculateMaxDrawdown(dailyEquity);

    const winningTrades = trades.filter(t => t.profit > 0);
    const losingTrades = trades.filter(t => t.profit < 0);
    const winRate = trades.length > 0 ? (winningTrades.length / trades.length) * 100 : 0;

    const avgWin = winningTrades.length > 0
      ? winningTrades.reduce((sum, t) => sum + t.profit, 0) / winningTrades.length
      : 0;
    const avgLoss = losingTrades.length > 0
      ? Math.abs(losingTrades.reduce((sum, t) => sum + t.profit, 0) / losingTrades.length)
      : 0;
    const profitLossRatio = avgLoss > 0 ? avgWin / avgLoss : 0;

    const sharpeRatio = this.calculateSharpeRatio(dailyEquity);
    const volatility = this.calculateVolatility(dailyEquity);

    const avgHoldingDays = trades.length > 0
      ? trades.reduce((sum, t) => sum + t.holding_days, 0) / trades.length
      : 0;

    const maxPositionCount = Math.max(
      ...dailyEquity.map((_, idx) => {
        // 计算每日持仓数（简化：从交易记录推断）
        const date = dailyEquity[idx].date;
        let count = 0;
        for (const trade of trades) {
          if (trade.entry_date <= date && trade.exit_date >= date) {
            count++;
          }
        }
        return count;
      })
    );

    return {
      strategy_id: strategy.id,
      start_date: startDate,
      end_date: endDate,
      initial_capital: initialCapital,
      final_capital: finalCapital,
      total_return: totalReturn,
      annual_return: annualReturn,
      max_drawdown: maxDrawdown,
      total_trades: trades.length,
      winning_trades: winningTrades.length,
      losing_trades: losingTrades.length,
      win_rate: winRate,
      profit_loss_ratio: profitLossRatio,
      sharpe_ratio: sharpeRatio,
      volatility: volatility,
      avg_holding_days: avgHoldingDays,
      max_position_count: maxPositionCount,
      trades,
      daily_equity: dailyEquity
    };
  }

  /**
   * 获取交易日列表
   */
  private async getTradingDays(startDate: string, endDate: string): Promise<string[]> {
    // TODO: 从数据库获取实际交易日
    // 当前简化实现：生成日期序列（跳过周末）
    const days: string[] = [];
    const start = new Date(startDate);
    const end = new Date(endDate);

    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const dayOfWeek = d.getDay();
      // 跳过周末
      if (dayOfWeek !== 0 && dayOfWeek !== 6) {
        days.push(d.toISOString().split('T')[0]);
      }
    }

    return days;
  }

  /**
   * 获取指定日期的股票数据
   */
  private async getStockDataForDate(
    symbols: string[],
    date: string
  ): Promise<Map<string, { price: number; name: string; indicators: any }>> {
    const result = new Map();

    for (const symbol of symbols) {
      try {
        // 🔥 快速检查：仅查本地DB，不触发API回源（次新股在上市前直接跳过）
        const realPrice = await this.factorLibrary.getLatestClosePriceLocal(symbol, date);
        if (realPrice <= 0) {
          continue; // 还没上市或无数据，跳过
        }

        // 并行计算技术指标
        const [rsi, ma5, ma10, ma20, ma60, macd, bb, fundamentals] = await Promise.all([
          this.factorLibrary.calculateRSIForSymbol(symbol, 14, date),
          this.factorLibrary.calculateMAForSymbol(symbol, 5, date),
          this.factorLibrary.calculateMAForSymbol(symbol, 10, date),
          this.factorLibrary.calculateMAForSymbol(symbol, 20, date),
          this.factorLibrary.calculateMAForSymbol(symbol, 60, date),
          this.factorLibrary.calculateMACDForSymbol(symbol, date),
          this.factorLibrary.calculateBollingerBands(symbol, 20, 2, date),
          this.factorLibrary.getFundamentals(symbol)
        ]);

        const price = realPrice;

        const indicators = {
          rsi,
          ma5,
          ma10,
          ma20,
          ma60,
          macd_dif: macd.dif,
          macd_dea: macd.dea,
          macd: macd.macd,
          bb_upper: bb.upper,
          bb_middle: bb.middle,
          bb_lower: bb.lower,
          volume_ratio: 1.0,
          atr: 0,
          // 基本面因子
          pe: fundamentals.pe,
          pb: fundamentals.pb,
          roe: fundamentals.roe,
          gross_margin: fundamentals.gross_margin,
          debt_ratio: fundamentals.debt_ratio,
        };

        result.set(symbol, {
          price,
          name: symbol,
          indicators
        });
      } catch (error) {
        // 跳过获取失败的股票
        console.error(`Failed to get data for ${symbol} on ${date}:`, error);
      }
    }

    return result;
  }

  /**
   * 判断是否应该退出持仓
   */
  private shouldExit(position: Position, currentPrice: number, strategy: QuantStrategy): boolean {
    const profitPct = ((currentPrice - position.entry_price) / position.entry_price);

    // 止损
    if (strategy.exit?.stop_loss) {
      if (profitPct <= -strategy.exit.stop_loss) {
        return true;
      }
    }

    // 止盈
    if (strategy.exit?.take_profit) {
      if (profitPct >= strategy.exit.take_profit) {
        return true;
      }
    }

    return false;
  }

  /**
   * 获取退出原因
   */
  private getExitReason(position: Position, currentPrice: number, strategy: QuantStrategy): string {
    const profitPct = ((currentPrice - position.entry_price) / position.entry_price) * 100;

    if (strategy.exit?.stop_loss && profitPct <= -strategy.exit.stop_loss * 100) {
      return `止损 (${profitPct.toFixed(2)}%)`;
    }

    if (strategy.exit?.take_profit && profitPct >= strategy.exit.take_profit * 100) {
      return `止盈 (${profitPct.toFixed(2)}%)`;
    }

    return '策略信号';
  }

  /**
   * 计算持仓规模
   */
  private calculatePositionSize(
    cash: number,
    price: number,
    strategy: QuantStrategy,
    currentPositions: number
  ): number {
    const maxStocks = strategy.position.max_stocks || 10;
    const maxPositionPct = strategy.position.max_position_pct || 0.1;

    // 使用等权重分配
    const positionValue = cash * maxPositionPct;
    return Math.floor(positionValue / price);
  }

  /**
   * 计算持仓市值
   */
  private calculatePositionValue(
    positions: Map<string, Position>,
    stockData: Map<string, { price: number; name: string; indicators: any }>
  ): number {
    let total = 0;
    for (const [symbol, position] of positions.entries()) {
      const data = stockData.get(symbol);
      if (data) {
        total += position.shares * data.price;
      }
    }
    return total;
  }

  /**
   * 计算回撤
   */
  private calculateDrawdown(dailyEquity: DailyEquity[], currentEquity: number): number {
    if (dailyEquity.length === 0) return 0;

    const peak = Math.max(...dailyEquity.map(d => d.total_equity), currentEquity);
    return ((currentEquity - peak) / peak) * 100;
  }

  /**
   * 计算最大回撤
   */
  private calculateMaxDrawdown(dailyEquity: DailyEquity[]): number {
    if (dailyEquity.length === 0) return 0;

    let maxDrawdown = 0;
    let peak = dailyEquity[0].total_equity;

    for (const day of dailyEquity) {
      if (day.total_equity > peak) {
        peak = day.total_equity;
      }
      const drawdown = ((day.total_equity - peak) / peak) * 100;
      if (drawdown < maxDrawdown) {
        maxDrawdown = drawdown;
      }
    }

    return Math.abs(maxDrawdown);
  }

  /**
   * 计算夏普比率
   */
  private calculateSharpeRatio(dailyEquity: DailyEquity[]): number {
    if (dailyEquity.length < 2) return 0;

    // 计算日收益率
    const dailyReturns: number[] = [];
    for (let i = 1; i < dailyEquity.length; i++) {
      const ret = (dailyEquity[i].total_equity - dailyEquity[i - 1].total_equity)
        / dailyEquity[i - 1].total_equity;
      dailyReturns.push(ret);
    }

    // 平均收益率
    const avgReturn = dailyReturns.reduce((sum, r) => sum + r, 0) / dailyReturns.length;

    // 标准差
    const variance = dailyReturns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0)
      / dailyReturns.length;
    const stdDev = Math.sqrt(variance);

    // 年化夏普比率（假设无风险利率为0，交易日252天）
    if (stdDev === 0) return 0;
    return (avgReturn / stdDev) * Math.sqrt(252);
  }

  /**
   * 计算波动率
   */
  private calculateVolatility(dailyEquity: DailyEquity[]): number {
    if (dailyEquity.length < 2) return 0;

    // 计算日收益率
    const dailyReturns: number[] = [];
    for (let i = 1; i < dailyEquity.length; i++) {
      const ret = (dailyEquity[i].total_equity - dailyEquity[i - 1].total_equity)
        / dailyEquity[i - 1].total_equity;
      dailyReturns.push(ret);
    }

    // 标准差
    const avgReturn = dailyReturns.reduce((sum, r) => sum + r, 0) / dailyReturns.length;
    const variance = dailyReturns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0)
      / dailyReturns.length;

    // 年化波动率
    return Math.sqrt(variance * 252) * 100;
  }

  /**
   * 计算天数差
   */
  private calculateDays(startDate: string, endDate: string): number {
    const start = new Date(startDate);
    const end = new Date(endDate);
    return Math.floor((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
  }

  /**
   * 计算年数
   */
  private calculateYears(startDate: string, endDate: string): number {
    const days = this.calculateDays(startDate, endDate);
    return days / 365;
  }
}
