/**
 * Subtractor（减法器）—— 投资账本切割引擎
 *
 * 核心职责：
 * 1. 从 trades.json + portfolio.json 提取所有交易记录
 * 2. 按周/月/全周期三个时间维度切割账本
 * 3. 对每笔交易核算：
 *    - 基础盈亏（已实现）
 *    - 机会成本（卖出价 vs 当前价）
 *    - 做T效应（cost averaging effect：通过做T降低持仓成本带来的收益）
 *    - 减仓效果（若没卖持有至今的对比）
 * 4. 输出 ComparisonResult 给补偿器做判断
 */

import type {
  ComparisonResult,
  TotalReturn,
  PeriodPerformance,
  DataQualityReport,
  OperationQualityReport,
  OperationQualityReview,
  OptimizationTip,
} from '../../types/evolution.js';

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { PriceService } from '../data/price-service.js';
import { StockDBService } from '../data/stock-db-service.js';

// ─── 数据模型 ───────────────────────────────────────────────────────────────

interface TradeRecord {
  id: number | string;
  symbol: string;
  name: string;
  action: 'buy' | 'sell';
  price: number;
  quantity: number;
  amount: number;
  fee: number;
  pnl: number | null;       // 卖出才有盈亏
  pnl_pct: number | null;
  date: string;             // ISO date string
  reason?: string;
}

interface HoldingPosition {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;         // CNH/CNH
  market: 'A' | 'HK';
  total_invested: number;
  added_date: string;
  original_cost: number;
  notes?: string;
}

/** 买入成本估算 —— 从持仓反推 */
interface EstimatedBuy {
  symbol: string;
  name: string;
  quantity: number;
  price: number;            // 估算买入价
  amount: number;
  date: string;             // 估算日期（用 added_date 或 notes 中信息）
  market: 'A' | 'HK';
}

/** FIFO批次 — 从买入记录构建的队列元素 */
interface FIFOBatch {
  symbol: string;
  name: string;
  buyDate: string;
  buyPrice: number;
  remainingQty: number;  // 该批次尚未被卖出的部分
  originalQty: number;   // 原始买入数量
  market: 'A' | 'HK';
}

/** 完整交易线（FIFO 配对的） */
interface MatchedTrade {
  symbol: string;
  name: string;
  buyDate: string;
  buyPrice: number;
  buyQuantity: number;
  sellDate: string | null;  // null = 仍持仓
  sellPrice: number | null;
  sellQuantity: number | null;
  realizedPnl: number | null;
  status: 'open' | 'closed';
  market: 'A' | 'HK';
  /** 做T标记：这笔卖出后30天内又有买入即视做T */
  dayTrade: boolean;
}

/** 当前实时价格（外部注入） */
interface CurrentPriceMap {
  [symbol: string]: number;
}

/**
 * 做T效应记录
 *
 * 做T（日内或短期高抛低吸）的核心价值是降低持仓成本。
 * 衡量方式：
 *   做T前成本价 vs 做T后加权成本价 × 当前持仓量 = 降本贡献
 *
 * 注意：做T不一定是当日完成，同一只股票在一段时期内的
 * 多次买卖都算是"做T"——只要最终该股票还有剩余持仓。
 */
interface DayTradeEffect {
  symbol: string;
  name: string;

  /** 做T前的原始成本价 */
  originalCostPrice: number;

  /** 做T后的加权平均成本价 */
  weightedAvgCost: number;

  /** 当前持仓量 */
  currentQuantity: number;

  /**
   * 做T贡献（最核心的指标）
   * = (原始成本价 - 加权平均价) × 当前持仓量
   * 正数 = 做T降本成功，为正收益
   * 负数 = 做T越做越高，为负收益
   */
  costReduction: number;

  /**
   * 做T方向说明
   * '高抛低吸' = 先卖后买(卖在高点买在低点)
   * '低吸高抛' = 先买后卖(买在低点卖在高点)
   * '复杂做T' = 多次买卖混合
   */
  direction: '高抛低吸' | '低吸高抛' | '复杂做T';

  /** 做T总交易笔数 */
  tradeCount: number;

  /** 做T产生的累计已实现盈亏 */
  realizedPnlFromTrades: number;

  /**
   * 置信度评估
   * high = 有实际交易记录验证
   * medium = 主要从 notes 提取
   * low = 仅从成本差推断，无交易证据
   */
  confidence: 'high' | 'medium' | 'low';
  confidenceNote?: string;

  /**
   * 做T对该股票的税务影响修正：
   * 如果做T过程产生了正的 realizedPnl，但税后/费后净收益更低
   * (暂时保留为 realizedPnlFromTrades，后续可加入手续费计算)
   */
}

// ─── 减法器引擎 ─────────────────────────────────────────────────────────────

export class Subtractor {
  private portfolioPath: string;
  private tradesPath: string;
  private priceService: PriceService;

  // 缓存
  private trades: TradeRecord[] = [];
  private holdings: HoldingPosition[] = [];
  private estimatedBuys: EstimatedBuy[] = [];
  private matchedTrades: MatchedTrade[] = [];
  private prices: CurrentPriceMap = {};

  constructor(options?: {
    portfolioPath?: string;
    tradesPath?: string;
    priceService?: PriceService;
  }) {
    const base = process.cwd();
    const piDir = join(base, '.pi-invest');
    this.portfolioPath = options?.portfolioPath ?? join(piDir, 'portfolio.json');
    this.tradesPath = options?.tradesPath ?? join(piDir, 'trades.json');
    this.priceService = options?.priceService ?? new PriceService(StockDBService.getInstance(piDir));
  }

  // ── 公开 API ──────────────────────────────────────────────────────────

  /**
   * 加载数据 + 执行减法器全流程
   * @param prices 当前实时价格（可选），不传则自动从数据库/API获取
   */
  async run(prices?: CurrentPriceMap): Promise<ComparisonResult> {
    this.prices = prices ?? {};
    this.loadAll();
    this.estimateMissingBuys();
    this.matchTrades();
    await this.enrichPrices(); // 自动填充缺失的当前价
    return this.buildComparisonResult();
  }

  /**
   * 仅获取总账（轻量调用）
   */
  async getTotalReturn(prices?: CurrentPriceMap): Promise<TotalReturn> {
    this.prices = prices ?? {};
    this.loadAll();
    this.estimateMissingBuys();
    this.matchTrades();
    await this.enrichPrices();
    return this.computeTotalReturn();
  }

  /**
   * 注入交易记录（替代文件读取，方便测试）
   */
  injectData(trades: TradeRecord[], holdings: HoldingPosition[]): void {
    this.trades = trades;
    this.holdings = holdings;
    this.estimatedBuys = [];
    this.matchedTrades = [];
  }

  // ── 内部 ──────────────────────────────────────────────────────────────

  private loadAll(): void {
    this.loadTrades();
    this.loadHoldings();
  }

  private loadTrades(): void {
    if (!existsSync(this.tradesPath)) {
      this.trades = [];
      return;
    }
    try {
      const raw = JSON.parse(readFileSync(this.tradesPath, 'utf-8'));
      this.trades = raw.trades ?? raw ?? [];
    } catch {
      this.trades = [];
    }
  }

  private loadHoldings(): void {
    if (!existsSync(this.portfolioPath)) {
      this.holdings = [];
      return;
    }
    try {
      const raw = JSON.parse(readFileSync(this.portfolioPath, 'utf-8'));
      this.holdings = raw.holdings ?? [];
    } catch {
      this.holdings = [];
    }
  }

  /**
   * 估算缺失的买入交易（从持仓反推）
   *
   * trades.json 只有卖出记录，缺少买入记录。
   * 这里从持仓数据反推买入交易，补全账本。
   */
  private estimateMissingBuys(): void {
    this.estimatedBuys = [];
    const estimated = new Set<string>();  // symbol_set to avoid duplicates

    for (const h of this.holdings) {
      // 如果有 total_invested 和 quantity，反推
      if (h.quantity > 0 && h.total_invested > 0) {
        const avgCost = h.total_invested / h.quantity;
        // 判断：trades.json 是否有对应的买入记录？
        const buyExists = this.trades.some(t =>
          t.symbol === h.symbol && t.action === 'buy'
        );

        if (!buyExists) {
          this.estimatedBuys.push({
            symbol: h.symbol,
            name: h.name,
            quantity: h.quantity,
            price: Math.round(avgCost * 100) / 100,
            amount: h.total_invested,
            date: h.added_date ? `${h.added_date}T00:00:00.000Z` : new Date().toISOString(),
            market: h.market as 'A' | 'HK',
          });
          estimated.add(h.symbol);
        }
      }
    }

    // 对卖出了但清仓了的股票：从 notes 中提取历史买入信息
    // 比如徐工卖完剩余400股，notes里有历史卖出价
    // 农行卖完存1100股，notes里有卖出记录
    // 神华卖完存400股，notes里有卖出记录
    // 这些卖出交易的买入端已经在 estimatedBuys 里的总投入中包含了
  }

  /**
   * FIFO 配对：用真实 FIFO 匹配买入 vs 卖出
   *
   * 核心策略：
   * 1. 如果 trades.json 有买入记录 → 直接从买入记录构建 FIFO 队列
   * 2. 如果没有买入记录 → 从持仓反推一条初始买入
   * 3. 按时间顺序处理所有卖出，FIFO 匹配
   * 4. 系统计算 realizedPnl（不依赖 trades.json 预填的 pnl 字段）
   * 5. 标记做T交易（卖出后30天内买入，且最终仍持有）
   */
  private matchTrades(): void {
    this.matchedTrades = [];

    // 按股票分组处理
    const stockSymbols = new Set<string>();
    for (const t of this.trades) stockSymbols.add(t.symbol);
    for (const h of this.holdings) stockSymbols.add(h.symbol);

    for (const symbol of stockSymbols) {
      this.matchTradesForSymbol(symbol);
    }
  }

  /** 对单只股票执行 FIFO 匹配 */
  private matchTradesForSymbol(symbol: string): void {
    const DAY_TRADE_WINDOW_MS = 30 * 24 * 60 * 60 * 1000;

    const stockTrades = this.trades
      .filter(t => t.symbol === symbol)
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

    const holding = this.holdings.find(h => h.symbol === symbol);
    const name = holding?.name || (stockTrades.length > 0 ? stockTrades[0].name : symbol);
    const market = (holding?.market || 'A') as 'A' | 'HK';

    // ── 构建 FIFO 买入批次队列 ──────────────────────────────────────
    const fifoQueue: FIFOBatch[] = [];

    // 先声明 sells 用于后续反推和匹配
    const sells = stockTrades.filter(t => t.action === 'sell');

    // 方式A：trades.json 的真实买入记录
    const buys = stockTrades.filter(t => t.action === 'buy');
    for (const b of buys) {
      fifoQueue.push({ symbol, name, buyDate: b.date, buyPrice: b.price, remainingQty: b.quantity, originalQty: b.quantity, market });
    }

    // 方式B：从持仓反推（买入记录不够覆盖卖出量+当前持仓时）
    const totalRealBuyQty = buys.reduce((s, b) => s + b.quantity, 0);
    const totalSellQty = sells.reduce((s, t) => s + t.quantity, 0);
    const currentQty = holding?.quantity || 0;
    const expectedBuyQty = totalSellQty + currentQty;

    if (totalRealBuyQty < expectedBuyQty) {
      const missingQty = expectedBuyQty - totalRealBuyQty;

      // 反推买入价：策略如下
      // 1. 优先从卖出记录的 pnl 反推（最精确的反推方式）
      // 2. 再用持仓的 avg_cost
      // 3. 已清仓用卖出均价的80%
      let buyPrice = 0;
      let buyDate = new Date().toISOString().substring(0, 10);

      // 从 pnl 反推：取第一笔有 pnl 的卖出记录
      // pnl = (sellPrice - costPrice) × qty → costPrice = sellPrice - pnl/qty
      const sellWithPnl = sells.find(t => t.pnl !== null && t.pnl !== undefined && t.quantity > 0);
      if (sellWithPnl) {
        buyPrice = sellWithPnl.price - (sellWithPnl.pnl! / sellWithPnl.quantity);
        buyPrice = Math.round(buyPrice * 100) / 100;
        buyDate = sellWithPnl.date;
      } else if (holding?.avg_cost && holding.avg_cost > 0) {
        // 用持仓的 avg_cost
        buyPrice = holding.avg_cost;
        buyDate = holding.added_date || buyDate;
      } else if (sells.length > 0) {
        // 完全无法反推，用卖出均价打8折
        const avgSellPrice = sells.reduce((s, t) => s + t.price * t.quantity, 0) /
          sells.reduce((s, t) => s + t.quantity, 0);
        buyPrice = Math.round(avgSellPrice * 0.8 * 100) / 100;
        buyDate = sells[0].date;
      }

      if (buyPrice > 0 && missingQty > 0) {
        fifoQueue.push({ symbol, name, buyDate, buyPrice, remainingQty: missingQty, originalQty: missingQty, market });
      }
    }

    // 按日期排序
    fifoQueue.sort((a, b) => new Date(a.buyDate).getTime() - new Date(b.buyDate).getTime());

    // ── 执行 FIFO 匹配（sells 已在上面声明）─ ──────────────────────
    for (const sell of sells) {
      let remainingSellQty = sell.quantity;
      const sellDate = sell.date;
      const sellPrice = sell.price;

      while (remainingSellQty > 0 && fifoQueue.length > 0) {
        const batch = fifoQueue[0];
        const qty = Math.min(remainingSellQty, batch.remainingQty);
        const costBasis = batch.buyPrice * qty;
        const proceeds = sellPrice * qty;
        const realizedPnl = proceeds - costBasis;

        // 做T判定：卖出后30天内该股有买入，且最终仍持有
        const buybackExists = stockTrades.some(t =>
          t.action === 'buy' &&
          new Date(t.date).getTime() > new Date(sellDate).getTime() &&
          new Date(t.date).getTime() <= new Date(sellDate).getTime() + DAY_TRADE_WINDOW_MS
        );

        this.matchedTrades.push({
          symbol, name,
          buyDate: batch.buyDate,
          buyPrice: batch.buyPrice,
          buyQuantity: qty,
          sellDate, sellPrice, sellQuantity: qty,
          realizedPnl: Math.round(realizedPnl * 100) / 100,
          status: 'closed',
          market,
          dayTrade: currentQty > 0 && buybackExists,
        });

        batch.remainingQty -= qty;
        remainingSellQty -= qty;

        if (batch.remainingQty <= 0) fifoQueue.shift();
      }
    }

    // ── 剩余 open 仓位 ─────────────────────────────────────────────
    for (const batch of fifoQueue) {
      if (batch.remainingQty > 0) {
        this.matchedTrades.push({
          symbol, name,
          buyDate: batch.buyDate,
          buyPrice: batch.buyPrice,
          buyQuantity: batch.remainingQty,
          sellDate: null, sellPrice: null, sellQuantity: null,
          realizedPnl: null,
          status: 'open',
          market,
          dayTrade: false,
        });
      }
    }
  }

  private getMarket(symbol: string): 'A' | 'HK' {
    // 港股通常 1-5 位数字或带 .HK
    if (/^\d{1,5}(\.HK)?$/i.test(symbol) && symbol.length <= 5) {
      return 'HK';
    }
    return 'A';
  }

  // ── 核心计算 ──────────────────────────────────────────────────────────

  /**
   * 构建完整的 ComparisonResult
   */
  private buildComparisonResult(): ComparisonResult {
    return {
      totalReturn: this.computeTotalReturn(),
      weeklyComparison: this.computePeriodPerformance('weekly'),
      monthlyComparison: this.computePeriodPerformance('monthly'),
      allTimeComparison: this.computeAllTimePerformance(),
      dataQuality: this.assessDataQuality(),
    };
  }

  /**
   * 总收益核算（完全基于 FIFO 匹配结果）
   *
   * 三种口径：
   * - totalInvestment（累积总投入）= 所有 FIFO buy 端买入金额总和（含已清仓）
   * - activeInvestment（活跃资金）= 仅当前 open 仓位的成本总和
   * - peakInvestment（峰值占用）= 历史账户余额最大值
   */
  private computeTotalReturn(): TotalReturn {
    let realizedPnL = 0;
    let unrealizedPnL = 0;
    let totalInvestment = 0;
    let activeInvestment = 0;

    // 用 FIFO 顺序模拟账户余额变化，求峰值
    let balance = 0;
    let peakBalance = 0;

    for (const mt of this.matchedTrades) {
      // 所有 buy 端都计入总投入
      totalInvestment += mt.buyPrice * mt.buyQuantity;
      // FIFO 余额模拟
      balance += mt.buyPrice * mt.buyQuantity;

      if (mt.status === 'closed') {
        realizedPnL += mt.realizedPnl ?? 0;
        // 卖出后余额减少（按买入成本扣减，而非卖出价——保守估计）
        balance -= mt.buyPrice * mt.buyQuantity;
      } else {
        // open position: 浮盈 = (当前价 - 成本价) × 数量
        const curPrice = this.getPrice(mt.symbol, mt.market);
        if (curPrice !== null) {
          const positionValue = curPrice * mt.buyQuantity;
          const costBasis = mt.buyPrice * mt.buyQuantity;
          unrealizedPnL += positionValue - costBasis;
        }
        activeInvestment += mt.buyPrice * mt.buyQuantity;
      }

      if (balance > peakBalance) peakBalance = balance;
    }

    const totalPnL = realizedPnL + unrealizedPnL;
    const activeReturnPct = activeInvestment > 0
      ? Math.round((totalPnL / activeInvestment) * 10000) / 100
      : 0;

    return {
      realizedPnL: Math.round(realizedPnL * 100) / 100,
      unrealizedPnL: Math.round(unrealizedPnL * 100) / 100,
      totalPnL: Math.round(totalPnL * 100) / 100,
      totalInvestment: Math.round(totalInvestment * 100) / 100,
      activeInvestment: Math.round(activeInvestment * 100) / 100,
      peakInvestment: Math.round(peakBalance * 100) / 100,
      totalReturnPct: totalInvestment > 0
        ? Math.round((totalPnL / totalInvestment) * 10000) / 100
        : 0,
      activeReturnPct,
    };
  }

  /**
   * 按周/月切割性能
   */
  private computePeriodPerformance(periodType: 'weekly' | 'monthly'): PeriodPerformance[] {
    const periods = new Map<string, {
      realizedPnL: number;
      tradeCount: number;
      winCount: number;
      earliestDate: string;
      latestDate: string;
    }>();

    // 从已平仓 trades 按时间聚合
    for (const mt of this.matchedTrades) {
      if (mt.status !== 'closed' || !mt.sellDate) continue;

      const date = new Date(mt.sellDate);
      const key = this.getPeriodKey(date, periodType);

      if (!periods.has(key)) {
        periods.set(key, {
          realizedPnL: 0,
          tradeCount: 0,
          winCount: 0,
          earliestDate: mt.sellDate,
          latestDate: mt.sellDate,
        });
      }

      const p = periods.get(key)!;
      p.realizedPnL += mt.realizedPnl ?? 0;
      p.tradeCount++;
      if ((mt.realizedPnl ?? 0) > 0) p.winCount++;
      if (mt.sellDate < p.earliestDate) p.earliestDate = mt.sellDate;
      if (mt.sellDate > p.latestDate) p.latestDate = mt.sellDate;
    }

    // 排序并输出
    const sortedKeys = Array.from(periods.keys()).sort();
    const results: PeriodPerformance[] = [];

    // 用 FIFO open 仓位总投入作为 baseCapital（activeInvestment）
    const totalReturn = this.computeTotalReturn();
    const baseCapital = totalReturn.activeInvestment;

    for (const key of sortedKeys) {
      const p = periods.get(key)!;
      const returnPct = baseCapital > 0
        ? (p.realizedPnL / baseCapital) * 100
        : 0;

      results.push({
        label: key,
        startDate: p.earliestDate,
        endDate: p.latestDate,
        realizedPnL: Math.round(p.realizedPnL * 100) / 100,
        unrealizedPnLChange: null,
        totalPnL: Math.round(p.realizedPnL * 100) / 100,
        beginningCapital: Math.round(baseCapital),
        returnPct: Math.round(returnPct * 100) / 100,
        tradeCount: p.tradeCount,
        winRate: p.tradeCount > 0 ? Math.round((p.winCount / p.tradeCount) * 100) / 100 : 0,
        reliability: 'partial',
      });
    }

    return results;
  }

  /**
   * 全周期性能
   */
  private computeAllTimePerformance(): PeriodPerformance {
    const totalReturn = this.computeTotalReturn();

    // 交易数据
    let tradeCount = 0;
    let winCount = 0;
    let earliestDate = '';
    let latestDate = '';

    for (const mt of this.matchedTrades) {
      tradeCount++;
      if (mt.status === 'closed') {
        if ((mt.realizedPnl ?? 0) > 0) winCount++;
        if (mt.sellDate) {
          if (!earliestDate || mt.sellDate < earliestDate) earliestDate = mt.sellDate;
          if (!latestDate || mt.sellDate > latestDate) latestDate = mt.sellDate;
        }
      } else {
        if (mt.buyDate) {
          if (!earliestDate || mt.buyDate < earliestDate) earliestDate = mt.buyDate;
          if (!latestDate || mt.buyDate > latestDate) latestDate = mt.buyDate;
        }
      }
    }

    return {
      label: '全周期',
      startDate: earliestDate,
      endDate: latestDate || new Date().toISOString(),
      realizedPnL: totalReturn.realizedPnL,
      unrealizedPnLChange: totalReturn.unrealizedPnL,
      totalPnL: totalReturn.totalPnL,
      beginningCapital: totalReturn.activeInvestment,
      returnPct: totalReturn.activeReturnPct,
      tradeCount,
      winRate: tradeCount > 0 ? Math.round((winCount / tradeCount) * 100) / 100 : 0,
      reliability: 'partial',
    };
  }

  /**
   * 数据完整性评估（增强版）
   */
  private assessDataQuality(): DataQualityReport {
    const sortedTrades = [...this.trades].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );

    const earliest = sortedTrades.length > 0 ? sortedTrades[0].date : null;
    const latest = sortedTrades.length > 0 ? sortedTrades[sortedTrades.length - 1].date : null;

    const warnings: string[] = [];
    const hasBuys = this.trades.some(t => t.action === 'buy');

    if (!hasBuys) {
      warnings.push('trades.json 缺少买入记录，买入数据从持仓反推（估算）');
    }
    if (this.estimatedBuys.length > 0) {
      warnings.push(`${this.estimatedBuys.length} 笔买入为估算数据，非实际成交记录`);
    }

    // 检查 notes 中的额外交易信息
    const notesTrades = this.holdings.filter(h => h.notes && /卖出|买入|成交/.test(h.notes));
    if (notesTrades.length > 0) {
      warnings.push(`${notesTrades.length} 只持仓的 notes 中包含未记录到 trades.json 的交易信息`);
    }

    // 增强：检查买入数量是否匹配卖出+持仓
    const buyQtyCheck = this.checkBuyQuantityMatch();
    if (buyQtyCheck.mismatches.length > 0) {
      warnings.push(`${buyQtyCheck.mismatches.length} 只股票的买入数量与卖出+持仓不匹配`);
    }

    // 增强：检查异常数据
    const anomalies = this.detectAnomalies();
    if (anomalies.length > 0) {
      warnings.push(`发现 ${anomalies.length} 条异常数据（价格或数量异常）`);
    }

    // 可靠性评级（增强版）
    let reliability: 'high' | 'medium' | 'low' = 'high';

    // 严重问题：无买入记录或大量估算
    if (!hasBuys || this.estimatedBuys.length > this.holdings.length * 0.5) {
      reliability = 'low';
    }
    // 中等问题：部分估算或数量不匹配
    else if (this.estimatedBuys.length > 0 || buyQtyCheck.mismatches.length > 0) {
      reliability = 'medium';
    }
    // 轻微问题：只有notes中的额外信息
    else if (notesTrades.length > 0) {
      reliability = 'medium';
    }

    let tradeCount = this.trades.length;

    return {
      earliestTradeDate: earliest,
      latestTradeDate: latest,
      tradeCount,
      positionCount: this.holdings.length,
      hasPortfolioData: this.holdings.length > 0,
      hasCompleteBuyRecords: hasBuys && buyQtyCheck.mismatches.length === 0,
      reliability,
      warnings,
    };
  }

  /**
   * 检查买入数量是否匹配卖出+持仓（新增）
   */
  private checkBuyQuantityMatch(): {
    mismatches: Array<{ symbol: string; buyQty: number; expectedQty: number; diff: number }>;
  } {
    const mismatches: Array<{ symbol: string; buyQty: number; expectedQty: number; diff: number }> = [];

    // 按股票分组
    const stockSymbols = new Set<string>();
    for (const t of this.trades) stockSymbols.add(t.symbol);
    for (const h of this.holdings) stockSymbols.add(h.symbol);

    for (const symbol of stockSymbols) {
      const buys = this.trades.filter(t => t.symbol === symbol && t.action === 'buy');
      const sells = this.trades.filter(t => t.symbol === symbol && t.action === 'sell');
      const holding = this.holdings.find(h => h.symbol === symbol);

      const totalBuyQty = buys.reduce((s, t) => s + t.quantity, 0);
      const totalSellQty = sells.reduce((s, t) => s + t.quantity, 0);
      const currentQty = holding?.quantity || 0;

      const expectedBuyQty = totalSellQty + currentQty;
      const diff = Math.abs(totalBuyQty - expectedBuyQty);

      // 允许1股的误差（四舍五入）
      if (diff > 1) {
        mismatches.push({
          symbol,
          buyQty: totalBuyQty,
          expectedQty: expectedBuyQty,
          diff,
        });
      }
    }

    return { mismatches };
  }

  /**
   * 检测异常数据（新增）
   */
  private detectAnomalies(): Array<{ type: string; symbol: string; detail: string }> {
    const anomalies: Array<{ type: string; symbol: string; detail: string }> = [];

    // 检查异常价格（过高或过低）
    for (const t of this.trades) {
      if (t.price <= 0) {
        anomalies.push({
          type: 'invalid_price',
          symbol: t.symbol,
          detail: `${t.action} 价格为 ${t.price}`,
        });
      } else if (t.price > 10000) {
        anomalies.push({
          type: 'suspicious_price',
          symbol: t.symbol,
          detail: `${t.action} 价格异常高: ${t.price}`,
        });
      }
    }

    // 检查异常数量
    for (const t of this.trades) {
      if (t.quantity <= 0) {
        anomalies.push({
          type: 'invalid_quantity',
          symbol: t.symbol,
          detail: `${t.action} 数量为 ${t.quantity}`,
        });
      }
    }

    // 检查卖出数量超过持仓（不考虑时间顺序的简单检查）
    for (const symbol of new Set(this.trades.map(t => t.symbol))) {
      const buys = this.trades.filter(t => t.symbol === symbol && t.action === 'buy');
      const sells = this.trades.filter(t => t.symbol === symbol && t.action === 'sell');

      const totalBuyQty = buys.reduce((s, t) => s + t.quantity, 0);
      const totalSellQty = sells.reduce((s, t) => s + t.quantity, 0);

      if (totalSellQty > totalBuyQty + 10) { // 允许10股误差
        anomalies.push({
          type: 'oversell',
          symbol,
          detail: `卖出 ${totalSellQty} 股超过买入 ${totalBuyQty} 股`,
        });
      }
    }

    return anomalies;
  }

  // ── 辅助函数 ──────────────────────────────────────────────────────────

  /**
   * 获取周期 key
   */
  private getPeriodKey(date: Date, type: 'weekly' | 'monthly'): string {
    if (type === 'weekly') {
      // ISO week: YYYY-WNN
      const yearStart = new Date(date.getFullYear(), 0, 1);
      const weekNum = Math.ceil(
        ((date.getTime() - yearStart.getTime()) / 86400000 + yearStart.getDay() + 1) / 7
      );
      return `${date.getFullYear()}-W${String(weekNum).padStart(2, '0')}`;
    } else {
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    }
  }

  /**
   * 获取当前价格
   */
  private getPrice(symbol: string, market: 'A' | 'HK'): number | null {
    if (this.prices[symbol]) return this.prices[symbol];

    // 尝试查找带 market 后缀的 key
    const altKey = market === 'HK' ? symbol.replace(/\.HK$/i, '') : symbol;
    if (altKey !== symbol && this.prices[altKey]) return this.prices[altKey];

    return null;
  }

  /**
   * 自动填充缺失的当前价（优化版：批量获取）
   *
   * roll=("已经清仓的股票" + "当前持仓的股票")
   * 遍历所有 matchedTrades 和 holdings，
   * 对 getPrice() 返回 null 的股票，批量从数据库/API获取实时价。
   */
  private async enrichPrices(): Promise<void> {
    // 收集需要获取价格的 symbols
    const needPrice = new Set<string>();

    // 1. 所有匹配过的股票（含已清仓）
    for (const mt of this.matchedTrades) {
      if (this.getPrice(mt.symbol, mt.market) === null) {
        needPrice.add(mt.symbol);
      }
    }

    // 2. 所有当前持仓
    for (const h of this.holdings) {
      if (this.getPrice(h.symbol, h.market as 'A' | 'HK') === null) {
        needPrice.add(h.symbol);
      }
    }

    if (needPrice.size === 0) return;

    console.log(`[Subtractor] 需要获取 ${needPrice.size} 个股票的价格...`);

    // 批量获取价格（数据库优先，接口兜底）
    const symbols = Array.from(needPrice);
    const priceMap = await this.priceService.getBatchPrices(symbols);

    // 更新价格缓存
    for (const [symbol, price] of priceMap) {
      this.prices[symbol] = price;
    }

    console.log(`[Subtractor] 成功获取 ${priceMap.size}/${needPrice.size} 个价格`);
  }

  // ── 高级分析：做T效应、机会成本、减仓效果 ──────────────────────────

  /**
   * 做T效应分析 — 基于 FIFO 匹配结果
   *
   * 做T = 同一只股票在持仓期间有卖出且之后仍有持仓，
   * 导致加权平均成本变化（或已实现盈亏反映在剩余头寸上）。
   *
   * 这里的做T检测不依赖 dayTrade 标记，而是看：
   * - 有卖出记录（从 trades.json）
   * - 目前仍持仓（从 portfolio.json）
   * 只要同时满足 → 卖出对剩余仓位产生了成本/盈亏影响
   *
   * costReduction = 所有卖出的 realizedPnl 之和
   * 因为做T的净盈利 = 成本降低，做T的净亏损 = 成本升高
   */
  analyzeDayTradeEffect(): DayTradeEffect[] {
    const results: DayTradeEffect[] = [];

    for (const h of this.holdings) {
      if (h.quantity <= 0) continue;

      // 该股票的所有卖出（从 matchedTrades 或 trades.json 取）
      const stockSells = this.trades.filter(t => t.symbol === h.symbol && t.action === 'sell');
      const stockMatchedSells = this.matchedTrades.filter(m =>
        m.symbol === h.symbol && m.status === 'closed'
      );

      const tradeCount = stockSells.length;
      if (tradeCount === 0 && h.original_cost === h.avg_cost) continue; // 无交易也无成本差，跳过

      // 总已实现盈亏 = FIFO匹配结果的和
      const totalClosedPnl = stockMatchedSells.reduce((s, m) => s + (m.realizedPnl ?? 0), 0);

      // 如果有交易也有持仓，所有退出仓位都算做T贡献
      const costReduction = stockSells.length > 0 ? totalClosedPnl : 0;

      // 如果也无交易也无成本差，跳过
      if (tradeCount === 0 && h.original_cost === h.avg_cost) continue;
      // 如果只有成本差无交易 → 置信度low
      const hasCostDiff = h.original_cost !== h.avg_cost;
      const hasTrades = tradeCount > 0;

      // 置信度
      const hasRealBuys = this.trades.some(t => t.symbol === h.symbol && t.action === 'buy');
      let confidence: 'high' | 'medium' | 'low';
      let confidenceNote: string | undefined;

      if (hasRealBuys) {
        confidence = 'high';
      } else if (hasTrades) {
        confidence = 'medium';
        confidenceNote = '买入记录从持仓反推，非实际成交记录';
      } else if (hasCostDiff) {
        confidence = 'low';
        confidenceNote = `仅从成本差推断(${h.original_cost}→${h.avg_cost})，无交易记录验证`;
      } else {
        continue;
      }

      // 方向判断
      let direction: '高抛低吸' | '低吸高抛' | '复杂做T' = '复杂做T';
      if (stockMatchedSells.length > 0) {
        const avgSellPrice = stockMatchedSells.reduce((s, m) => s + (m.sellPrice ?? 0) * m.sellQuantity!, 0) /
          stockMatchedSells.reduce((s, m) => s + m.sellQuantity!, 0);
        const avgBuyPrice = stockMatchedSells.reduce((s, m) => s + m.buyPrice * m.buyQuantity, 0) /
          stockMatchedSells.reduce((s, m) => s + m.buyQuantity, 0);
        if (avgSellPrice > avgBuyPrice) direction = '高抛低吸';
        else if (avgSellPrice < avgBuyPrice) direction = '低吸高抛';
      }

      results.push({
        symbol: h.symbol,
        name: h.name,
        originalCostPrice: h.original_cost,
        weightedAvgCost: h.avg_cost,
        currentQuantity: h.quantity,
        costReduction: Math.round(costReduction * 100) / 100,
        direction,
        tradeCount: hasTrades ? tradeCount : 0,
        realizedPnlFromTrades: Math.round(totalClosedPnl * 100) / 100,
        confidence,
        confidenceNote,
      });
    }

    return results.sort((a, b) => Math.abs(b.costReduction) - Math.abs(a.costReduction));
  }

  /** 从 notes 中提取卖出信息 */
  private extractSellInfoFromNotes(notes: string, symbol: string): number {
    // 尝试匹配模式: "卖出N股@价格" 或 "卖N股@价格"（含中文逗号前后）
    // 如: "2026-05-08 卖出700股@10.30；2026-05-11 卖出400股@10.97"
    // 如: "5/12卖300股@45.20，5/13卖300股@45.01"
    const sellPattern = /卖(?:出)?\s*(\d+)\s*股@([\d.]+)/g;
    const noteSells: Array<{ qty: number; price: number }> = [];
    let match;
    while ((match = sellPattern.exec(notes)) !== null) {
      noteSells.push({
        qty: parseInt(match[1]),
        price: parseFloat(match[2]),
      });
    }

    // 找到对应持仓的原始成本价
    const holding = this.holdings.find(h => h.symbol === symbol);
    if (!holding) return 0;

    const costPrice = holding.original_cost || holding.avg_cost;
    if (costPrice <= 0) return 0;

    // 每笔卖出 = (卖价 - 成本价) × 数量
    // ⚠️ 注意：当 original_cost === avg_cost 时（即 costDiffers=false），
    // 这里返回的是"止盈收益"而非真正的"成本降低"。
    // 真正的做T降本需要卖出后低价买回的完整交易链。
    // 消费方应结合 confidence 字段判断语义。
    let totalPnl = 0;
    for (const sell of noteSells) {
      totalPnl += (sell.price - costPrice) * sell.qty;
    }

    return totalPnl;
  }

  /**
   * 机会成本分析：卖出价 vs 当前价
   *
   * 返回每笔卖出的卖飞损失/正确卖出的额外收益
   */
  analyzeOpportunityCost(): Array<{
    symbol: string;
    name: string;
    sellDate: string;
    sellPrice: number;
    quantity: number;
    currentPrice: number | null;
    /** >0 = 卖对了（现价比卖价低），<0 = 卖飞了（现价比卖价高） */
    opportunityGain: number;
    label: '卖对' | '卖飞';
  }> {
    const results: Array<{
      symbol: string;
      name: string;
      sellDate: string;
      sellPrice: number;
      quantity: number;
      currentPrice: number | null;
      opportunityGain: number;
      label: '卖对' | '卖飞';
    }> = [];

    for (const mt of this.matchedTrades) {
      if (mt.status !== 'closed' || !mt.sellPrice) continue;

      const curPrice = this.getPrice(mt.symbol, mt.market);
      if (curPrice === null) continue;

      // opp_gain = (卖价 - 现价) × 数量
      // 正 = 卖对了（卖价比现价高，少跌了/多赚了）
      // 负 = 卖飞了（现价比卖价高，少赚了）
      const oppGain = (mt.sellPrice - curPrice) * mt.sellQuantity!;

      results.push({
        symbol: mt.symbol,
        name: mt.name,
        sellDate: mt.sellDate || '',
        sellPrice: mt.sellPrice,
        quantity: mt.sellQuantity || 0,
        currentPrice: curPrice,
        opportunityGain: Math.round(oppGain * 100) / 100,
        label: oppGain > 0 ? '卖对' : '卖飞',
      });
    }

    return results.sort((a, b) => a.opportunityGain - b.opportunityGain);
  }

  /**
   * 减仓避损分析：如果卖出部分没卖，持有至今会怎样
   *
   * 基于 FIFO 匹配结果，使用真实的买入成本价。
   * 做T交易从"减仓避损"视角单独标注。
   */
  analyzeHedgeEffect(): Array<{
    symbol: string;
    name: string;
    sellDate: string;
    sellPrice: number;
    quantity: number;
    costPrice: number;
    realizedPnl: number;
    /** 如果持有至今的盈亏（用同样的FIFO成本价算） */
    wouldBePnl: number;
    /** >0 = 减仓减少损失，<0 = 卖早了少赚 */
    savedByCut: number;
    label: '减仓正确' | '卖早了' | '止盈正确' | '做T';
    dayTrade: boolean;
  }> {
    const results: Array<{
      symbol: string;
      name: string;
      sellDate: string;
      sellPrice: number;
      quantity: number;
      costPrice: number;
      realizedPnl: number;
      wouldBePnl: number;
      savedByCut: number;
      label: '减仓正确' | '卖早了' | '止盈正确' | '做T';
      dayTrade: boolean;
    }> = [];

    for (const mt of this.matchedTrades) {
      if (mt.status !== 'closed' || !mt.sellPrice) continue;

      const costPrice = mt.buyPrice;
      if (costPrice === 0) continue;

      const curPrice = this.getPrice(mt.symbol, mt.market);
      const realizedPnl = mt.realizedPnl ?? 0;

      let label: '减仓正确' | '卖早了' | '止盈正确' | '做T';
      let wouldBePnl = 0;
      let savedByCut = 0;

      if (mt.dayTrade) {
        label = '做T';
        if (curPrice !== null) {
          wouldBePnl = (curPrice - costPrice) * mt.sellQuantity!;
          savedByCut = realizedPnl - wouldBePnl;
        }
      } else {
        // 如果当前没持仓（已清仓），用最后一次卖价估算"持有至清仓"的效果
        if (curPrice !== null) {
          wouldBePnl = (curPrice - costPrice) * mt.sellQuantity!;
        }
        savedByCut = realizedPnl - wouldBePnl;
        if (savedByCut > 0 && realizedPnl > 0) label = '止盈正确';
        else if (savedByCut > 0 && realizedPnl <= 0) label = '减仓正确';
        else if (realizedPnl > 0 && savedByCut >= -500) label = '止盈正确'; // 小幅度卖飞仍算止盈正确
        else label = '卖早了';
      }

      results.push({
        symbol: mt.symbol,
        name: mt.name,
        sellDate: mt.sellDate || '',
        sellPrice: mt.sellPrice,
        quantity: mt.sellQuantity || 0,
        costPrice,
        realizedPnl: Math.round(realizedPnl * 100) / 100,
        wouldBePnl: Math.round(wouldBePnl * 100) / 100,
        savedByCut: Math.round(savedByCut * 100) / 100,
        label,
        dayTrade: mt.dayTrade,
      });
    }

    return results;
  }

  /**
   * 全部利润归因汇总
   *
   * 将总利润拆解为四个维度的贡献：
   * 1. 做T降本贡献 — 同一只股票内 T 操作带来的成本下降
   * 2. 浮盈贡献 — 剩余持仓从做T后成本到当前价的变化
   * 3. 已实现盈亏 — 已经落袋的净盈亏(含做T过程中产生的)
   * 4. 机会成本影响 — 卖出 vs 持有的净差异
   */
  analyzeAllAttribution(): {
    totalPnL: number;
    attribution: {
      /** 做T降本带来的收益 */
      dayTradeCostReduction: { amount: number; details: DayTradeEffect[] };
      /** 剩余持仓从加权成本到当前价的浮盈 */
      remainingFloatPnL: { amount: number; details: Array<{ symbol: string; name: string; value: number }> };
      /** 已实现盈亏（所有已平仓的净盈亏，含做T中的买卖） */
      realizedPnl: { amount: number; details: Array<{ symbol: string; name: string; value: number }> };
      /** 机会成本净值 = 卖对总和 - 卖飞总和 */
      opportunityCost: { amount: number; details: Array<{ symbol: string; name: string; value: number; label: string }> };
    };
  } {
    // 1. 做T降本
    const dayTradeEffects = this.analyzeDayTradeEffect();
    const totalCostReduction = dayTradeEffects.reduce((s, d) => s + d.costReduction, 0);

    // 2. 浮盈：从加权成本价到当前价
    const remainingFloatDetails: Array<{ symbol: string; name: string; value: number }> = [];
    let totalFloatPnL = 0;
    for (const h of this.holdings) {
      if (h.quantity <= 0) continue;
      const curPrice = this.getPrice(h.symbol, h.market as 'A' | 'HK');
      if (curPrice === null) continue;
      const floatPnL = (curPrice - h.avg_cost) * h.quantity;
      totalFloatPnL += floatPnL;
      remainingFloatDetails.push({
        symbol: h.symbol,
        name: h.name,
        value: Math.round(floatPnL * 100) / 100,
      });
    }

    // 3. 已实现盈亏（按股票汇总）
    const realizedDetails: Array<{ symbol: string; name: string; value: number }> = [];
    let totalRealized = 0;
    const symbolRealized = new Map<string, { name: string; value: number }>();
    for (const t of this.trades) {
      if (t.action !== 'sell' || t.pnl === null) continue;
      const existing = symbolRealized.get(t.symbol);
      if (existing) {
        existing.value += t.pnl;
      } else {
        symbolRealized.set(t.symbol, { name: t.name, value: t.pnl });
      }
    }
    for (const [symbol, info] of symbolRealized) {
      totalRealized += info.value;
      realizedDetails.push({
        symbol,
        name: info.name,
        value: Math.round(info.value * 100) / 100,
      });
    }

    // 4. 机会成本
    const oppCostDetails = this.analyzeOpportunityCost();
    const totalOppCost = oppCostDetails.reduce((s, o) => s + o.opportunityGain, 0);

    const totalPnL = totalCostReduction + totalFloatPnL + totalRealized;

    return {
      totalPnL: Math.round(totalPnL * 100) / 100,
      attribution: {
        dayTradeCostReduction: {
          amount: Math.round(totalCostReduction * 100) / 100,
          details: dayTradeEffects,
        },
        remainingFloatPnL: {
          amount: Math.round(totalFloatPnL * 100) / 100,
          details: remainingFloatDetails.sort((a, b) => a.value - b.value),
        },
        realizedPnl: {
          amount: Math.round(totalRealized * 100) / 100,
          details: realizedDetails.sort((a, b) => a.value - b.value),
        },
        opportunityCost: {
          amount: Math.round(totalOppCost * 100) / 100,
          details: oppCostDetails.map(o => ({
            symbol: o.symbol,
            name: o.name,
            value: o.opportunityGain,
            label: o.label,
          })),
        },
      },
    };
  }

  /**
   * 按维度分组分析结果
   */
  summarizeByDimension(): {
    baseSettlement: { realizedPnL: number; winRate: number; totalTrades: number; dayTradeOnly: { pnl: number; count: number; winRate: number } };
    opportunityCost: { totalGain: number; totalLoss: number; netOpportunity: number };
    hedgeEffect: { totalSaved: number; totalMissed: number; netHedge: number; savedByDayTrade: number };
    dayTradeEffect: { totalCostReduction: number; tradeCount: number; topPerformers: DayTradeEffect[] };
  } {
    const oppCost = this.analyzeOpportunityCost();
    const hedge = this.analyzeHedgeEffect();
    const dayTrade = this.analyzeDayTradeEffect();

    const oppGain = oppCost.filter(o => o.label === '卖对').reduce((s, o) => s + o.opportunityGain, 0);
    const oppLoss = oppCost.filter(o => o.label === '卖飞').reduce((s, o) => s + Math.abs(o.opportunityGain), 0);

    const saved = hedge.filter(h => h.savedByCut > 0 && !h.dayTrade).reduce((s, h) => s + h.savedByCut, 0);
    const missed = hedge.filter(h => h.savedByCut <= 0 && !h.dayTrade).reduce((s, h) => s + Math.abs(h.savedByCut), 0);
    const savedByDayTrade = hedge.filter(h => h.dayTrade).reduce((s, h) => s + (h.realizedPnl > 0 ? h.realizedPnl : 0), 0);

    const totalCostReduction = dayTrade.reduce((s, d) => s + d.costReduction, 0);
    const totalTradeCount = dayTrade.reduce((s, d) => s + d.tradeCount, 0);

    const closedTrades = this.matchedTrades.filter(mt => mt.status === 'closed');
    const realizedPnL = closedTrades.reduce((s, mt) => s + (mt.realizedPnl ?? 0), 0);
    const winCount = closedTrades.filter(mt => (mt.realizedPnl ?? 0) > 0).length;

    // 做T单独统计：用 analyzeDayTradeEffect 的结果（更准确，涵盖所有持股期间的卖出）
    const dayTradeData = this.analyzeDayTradeEffect();
    const dayTradeCount = dayTradeData.reduce((s, d) => s + d.tradeCount, 0);
    const dayTradePnl = dayTradeData.reduce((s, d) => s + d.realizedPnlFromTrades, 0);
    const dayTradeWinCount = dayTradeData.filter(d => d.costReduction > 0).length;
    const dayTradeTotal = dayTradeData.filter(d => d.tradeCount > 0).length;

    return {
      baseSettlement: {
        realizedPnL: Math.round(realizedPnL * 100) / 100,
        winRate: closedTrades.length > 0
          ? Math.round((winCount / closedTrades.length) * 100) / 100
          : 0,
        totalTrades: closedTrades.length,
        dayTradeOnly: {
          pnl: Math.round(dayTradePnl * 100) / 100,
          count: dayTradeCount,
          winRate: dayTradeTotal > 0
            ? Math.round((dayTradeWinCount / dayTradeTotal) * 100) / 100
            : 0,
        },
      },
      opportunityCost: {
        totalGain: Math.round(oppGain * 100) / 100,
        totalLoss: Math.round(oppLoss * 100) / 100,
        netOpportunity: Math.round((oppGain - oppLoss) * 100) / 100,
      },
      hedgeEffect: {
        totalSaved: Math.round(saved * 100) / 100,
        totalMissed: Math.round(missed * 100) / 100,
        netHedge: Math.round((saved - missed) * 100) / 100,
        savedByDayTrade: Math.round(savedByDayTrade * 100) / 100,
      },
      dayTradeEffect: {
        totalCostReduction: Math.round(totalCostReduction * 100) / 100,
        tradeCount: totalTradeCount,
        topPerformers: dayTrade.slice(0, 5),
      },
    };
  }

  /**
   * 操作质量评估：分析已平仓股票的卖出执行质量
   *
   * 基于 FIFO 匹配结果，对每只有封闭交易的股票评估：
   * 1. 分批止盈的卖出价格梯度是否合理（是否后卖出价低于前卖出价）
   * 2. 高点捕获率（卖出价在区间内的相对位置）
   * 3. 仓位分配是否均匀（单次卖出占比是否过大/过小）
   *
   * 输出优化建议供后续操作参考。
   */
  analyzeOperationQuality(): OperationQualityReport {
    // 按 symbol 分组 closed 交易
    const closedBySymbol = new Map<string, MatchedTrade[]>();
    for (const mt of this.matchedTrades) {
      if (mt.status !== 'closed') continue;
      if (!closedBySymbol.has(mt.symbol)) closedBySymbol.set(mt.symbol, []);
      closedBySymbol.get(mt.symbol)!.push(mt);
    }

    const stocks: OperationQualityReview[] = [];
    const allTips: OptimizationTip[] = [];
    let totalOptimizablePnL = 0;

    for (const [symbol, trades] of closedBySymbol) {
      const name = trades[0].name;
      const isClosed = !this.holdings.some(h => h.symbol === symbol && h.quantity > 0);

      // ── 1. 卖出价排序 & 统计 ────────────────────────────────────
      const sellsSorted = [...trades]
        .filter(m => m.sellPrice !== null && m.sellQuantity !== null)
        .sort((a, b) => new Date(a.sellDate || '').getTime() - new Date(b.sellDate || '').getTime());

      if (sellsSorted.length < 2) continue; // 单笔卖出不评估

      const sellPrices = sellsSorted.map(m => m.sellPrice!);
      const sellQtys = sellsSorted.map(m => m.sellQuantity!);
      const totalQty = sellQtys.reduce((s, q) => s + q, 0);
      const avgSellPrice = sellPrices.reduce((s, p, i) => s + p * sellQtys[i], 0) / totalQty;
      const maxPrice = Math.max(...sellPrices);
      const minPrice = Math.min(...sellPrices);
      const priceSpread = Math.round((maxPrice - minPrice) * 100) / 100;

      // ── 2. 分批止盈梯度评分 ─────────────────────────────────────
      // 理想分批止盈：售价递进或至少不倒退
      let regressions = 0;
      for (let i = 1; i < sellPrices.length; i++) {
        if (sellPrices[i] < sellPrices[i - 1]) regressions++;
      }
      // 梯度分：每次倒退扣 25 分
      const batchExitScore = Math.max(0, Math.round(100 - regressions * 25));

      // ── 3. 高点捕获率 ───────────────────────────────────────────
      // 加权平均售价在 [min, max] 区间的位置
      // 100% = 全部卖出在最高价，0% = 全部卖出在最低价
      const range = maxPrice - minPrice;
      const peakCapturePct = range > 0
        ? Math.round(((avgSellPrice - minPrice) / range) * 100)
        : 100;

      // ── 4. 优化提示生成 ─────────────────────────────────────────
      const tips: OptimizationTip[] = [];

      // 梯度倒退提示
      if (regressions > 0) {
        const regressionExamples: string[] = [];
        for (let i = 1; i < sellPrices.length; i++) {
          if (sellPrices[i] < sellPrices[i - 1]) {
            regressionExamples.push(
              `第${i + 1}笔¥${sellPrices[i]} < 第${i}笔¥${sellPrices[i - 1]}（低¥${(sellPrices[i - 1] - sellPrices[i]).toFixed(2)}）`
            );
          }
        }
        tips.push({
          type: 'batch_price_regression',
          severity: 'improvement',
          message: `分批止盈出现${regressions}次价格倒退`,
          detail: regressionExamples.join('；'),
          data: {
            pnlImpact: Math.round(regressionExamples.length * priceSpread * 50),
          },
        });
      }

      // 高位卖出占比过低提示
      if (peakCapturePct < 60 && priceSpread > 0.5) {
        tips.push({
          type: 'sold_below_peak',
          severity: 'warning',
          message: `卖出均价¥${avgSellPrice.toFixed(2)}仅占区间高位${peakCapturePct}%，最高达¥${maxPrice}`,
          detail: `如果均价能提升到¥${((minPrice + maxPrice) / 2).toFixed(2)}以上，每100股多赚¥${Math.round(((minPrice + maxPrice) / 2 - avgSellPrice) * 100) / 100}`,
          data: {
            price: avgSellPrice,
            suggestedPrice: Math.round((minPrice + maxPrice) / 2 * 100) / 100,
            pnlImpact: Math.round(((minPrice + maxPrice) / 2 - avgSellPrice) * totalQty),
          },
        });
      }

      // 仓位分配提示
      const maxBatchRatio = Math.max(...sellQtys) / totalQty;
      if (maxBatchRatio > 0.5 && sellsSorted.length > 1) {
        tips.push({
          type: 'uneven_position_sizing',
          severity: 'info',
          message: `单次卖出占比${(maxBatchRatio * 100).toFixed(0)}%，可以考虑更均匀的分批`,
          detail: `最大笔${Math.max(...sellQtys)}股 / 总计${totalQty}股`,
          data: {
            quantity: Math.max(...sellQtys),
          },
        });
      }

      // 执行质量好
      if (tips.length === 0 || (tips.length === 1 && tips[0].type === 'uneven_position_sizing')) {
        tips.push({
          type: 'good_execution',
          severity: 'info',
          message: `执行质量好，均价¥${avgSellPrice.toFixed(2)}覆盖区间${peakCapturePct}%`,
        });
      }

      // ── 5. 综合评分 ─────────────────────────────────────────────
      let overallScore = batchExitScore * 0.4 + peakCapturePct * 0.6;
      // 仓位不均扣分
      if (maxBatchRatio > 0.6) overallScore -= 10;
      overallScore = Math.max(0, Math.min(100, Math.round(overallScore)));

      const pnlFromRegressions = tips
        .filter(t => t.data?.pnlImpact && t.data.pnlImpact > 0)
        .reduce((s, t) => s + (t.data?.pnlImpact || 0), 0);
      totalOptimizablePnL += pnlFromRegressions;

      stocks.push({
        overallScore,
        symbol,
        name,
        isClosed,
        batchExitScore,
        peakCapturePct,
        priceSpread,
        avgSellPrice: Math.round(avgSellPrice * 100) / 100,
        optimizationTips: tips,
      });

      allTips.push(...tips);
    }

    stocks.sort((a, b) => a.overallScore - b.overallScore);
    const averageScore = stocks.length > 0
      ? Math.round(stocks.reduce((s, st) => s + st.overallScore, 0) / stocks.length)
      : 0;

    return {
      stocks,
      averageScore,
      topOptimizations: allTips
        .filter(t => t.type !== 'good_execution')
        .slice(0, 3),
      totalOptimizablePnL,
    };
  }
}

// ─── 便捷函数 ───────────────────────────────────────────────────────────────

/**
 * 一键调用减法器
 */
export async function runSubtractor(prices?: CurrentPriceMap): Promise<ComparisonResult> {
  const subt = new Subtractor();
  return await subt.run(prices);
}

/**
 * 全方位总结（含做T效应）
 */
export async function getSubtractorSummary(prices?: CurrentPriceMap): Promise<{
  totalReturn: TotalReturn;
  summary: ReturnType<Subtractor['summarizeByDimension']>;
  attribution: ReturnType<Subtractor['analyzeAllAttribution']>;
  opportunityCost: ReturnType<Subtractor['analyzeOpportunityCost']>;
  hedgeEffect: ReturnType<Subtractor['analyzeHedgeEffect']>;
  dayTradeEffect: DayTradeEffect[];
}> {
  const subt = new Subtractor();
  await subt.run(prices);
  return {
    totalReturn: subt['computeTotalReturn'](),
    summary: subt.summarizeByDimension(),
    attribution: subt.analyzeAllAttribution(),
    opportunityCost: subt.analyzeOpportunityCost(),
    hedgeEffect: subt.analyzeHedgeEffect(),
    dayTradeEffect: subt.analyzeDayTradeEffect(),
  };
}
