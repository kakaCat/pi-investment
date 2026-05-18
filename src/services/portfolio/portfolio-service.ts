/**
 * PortfolioService — 持仓管理服务
 *
 * 负责：
 *   1. 持仓文件 .pi-invest/portfolio.json 的读写（CRUD）
 *   2. 结合实时行情计算当前浮盈浮亏
 *   3. 格式化持仓摘要供 agent 和复盘使用
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { get_stock_realtime_price, get_hk_stock_price } from "../../infrastructure/akshare-ts/index.js";
import { chinaDate, chinaDateTime } from "../../utils/china-time.js";
import { FileLockService } from "../file-lock.service.js";
import { FxRateServiceAdapter } from "../fx-rate-service-adapter.js";

// ─── 数据结构 ──────────────────────────────────────────────────────────────

export interface Holding {
  symbol: string;      // 股票代码（6位A股 或 5位港股）
  name: string;        // 股票名称（可从行情更新）
  quantity: number;    // 持股数量（股）
  avg_cost: number;    // 持仓均价（元/港元）
  avg_cost_hkd?: number;         // 港币成本（HKD），仅港股
  purchase_fx_rate?: number;     // 买入时汇率（HKD→CNY），仅港股
  market: "A" | "HK";  // 市场类型
  notes: string;       // 备注（如：分批建仓批次、操作背景等）
  added_date: string;  // 首次录入日期
  stop_loss?: number | null;  // 止损价
  target_price?: number | null;  // 目标价
  sector?: string;     // 行业
  buy_reason?: string; // 买入理由
}

export interface PortfolioFile {
  holdings: Holding[];
  last_updated: string;
}

export interface HoldingWithPnL extends Holding {
  current_price: number;
  current_price_hkd?: number;    // 当前港币价格
  current_fx_rate?: number;      // 当前汇率
  change_pct: number;      // 今日涨跌幅
  pnl_pct: number;         // 持仓盈亏%
  pnl_amount: number;      // 持仓盈亏额（元）
  market_value: number;    // 当前市值
}

export interface PortfolioSnapshot {
  holdings: HoldingWithPnL[];
  total_cost: number;      // 总成本
  total_value: number;     // 当前总市值
  total_pnl: number;       // 总浮盈浮亏（元）
  total_pnl_pct: number;   // 总盈亏比例
  as_of: string;
}

export interface SellResult {
  success: boolean;
  message: string;
  symbol: string;
  sellPrice: number;
  quantity: number;
  remaining: number;
  pnlAmount: number;
  pnlPct: number;
  tradeRecorded: boolean;
  updatedHolding?: Holding;           // 更新后的持仓（部分卖出时）
  portfolioSnapshot?: PortfolioSnapshot;  // 完整持仓快照（供 LLM 决策）
}

// ─── 工具函数 ──────────────────────────────────────────────────────────────

function today(): string {
  return chinaDate();
}

function nowStr(): string {
  return chinaDateTime();
}

function roundN(v: number, n = 2): number {
  return Math.round(v * Math.pow(10, n)) / Math.pow(10, n);
}

export function buildPortfolioSnapshotFromQuotes(
  holdings: Holding[],
  priceResults: Array<Record<string, unknown>>,
  fxRate: number = 0.88
): PortfolioSnapshot {
  if (holdings.length === 0) {
    return { holdings: [], total_cost: 0, total_value: 0, total_pnl: 0, total_pnl_pct: 0, as_of: today() };
  }

  let totalCost = 0;
  let totalValue = 0;

  const enriched: HoldingWithPnL[] = holdings.map((h, i) => {
    const rt = priceResults[i] ?? {};

    if (h.market === "HK") {
      // HK stock logic: convert HKD price to CNY
      const currentPriceHKD = Number(rt.price ?? 0);
      const currentPriceCNY = currentPriceHKD * fxRate;
      const changePct = Number(rt.change_pct ?? rt.pct_chg ?? 0);
      const marketValue = roundN(currentPriceCNY * h.quantity);
      const cost = roundN(h.avg_cost * h.quantity);
      const pnlAmt = roundN(marketValue - cost);
      const pnlPct = cost > 0 ? roundN((pnlAmt / cost) * 100) : 0;

      totalCost += cost;
      totalValue += marketValue;

      return {
        ...h,
        name: String(rt.name ?? h.name),
        current_price: currentPriceCNY,
        current_price_hkd: currentPriceHKD,
        current_fx_rate: fxRate,
        change_pct: roundN(changePct),
        pnl_pct: pnlPct,
        pnl_amount: pnlAmt,
        market_value: marketValue,
      };
    } else {
      // A-share logic (unchanged)
      const curPrice = Number(rt.price ?? rt.current_price ?? 0);
      const changePct = Number(rt.change_pct ?? rt.pct_chg ?? 0);
      const pnlPct = h.avg_cost > 0 ? roundN((curPrice - h.avg_cost) / h.avg_cost * 100) : 0;
      const pnlAmt = roundN((curPrice - h.avg_cost) * h.quantity);
      const marketValue = roundN(curPrice * h.quantity);
      const cost = roundN(h.avg_cost * h.quantity);
      totalCost += cost;
      totalValue += marketValue;

      return {
        ...h,
        name: String(rt.name ?? h.name),
        current_price: curPrice,
        change_pct: roundN(changePct),
        pnl_pct: pnlPct,
        pnl_amount: pnlAmt,
        market_value: marketValue,
      };
    }
  });

  const totalPnl = roundN(totalValue - totalCost);
  const totalPnlPct = totalCost > 0 ? roundN(totalPnl / totalCost * 100) : 0;

  return {
    holdings: enriched,
    total_cost: totalCost,
    total_value: totalValue,
    total_pnl: totalPnl,
    total_pnl_pct: totalPnlPct,
    as_of: today(),
  };
}

// ─── PortfolioService ──────────────────────────────────────────────────────

export class PortfolioService {
  private filePath: string;
  private tradeService?: any;
  private fxRateService: FxRateServiceAdapter;

  constructor(piDir: string) {
    this.filePath = join(piDir, "portfolio.json");
    this.fxRateService = new FxRateServiceAdapter(piDir);
    mkdirSync(piDir, { recursive: true });
    this.ensureFile();
  }

  /**
   * 设置 TradeService 依赖（用于高层业务方法）
   */
  setTradeService(tradeService: any): void {
    this.tradeService = tradeService;
  }

  // ── 文件初始化 ────────────────────────────────────────────────────────────

  private ensureFile(): void {
    if (!existsSync(this.filePath)) {
      const empty: PortfolioFile = { holdings: [], last_updated: "" };
      writeFileSync(this.filePath, JSON.stringify(empty, null, 2), "utf-8");
      console.log(`[portfolio] 初始化持仓文件: ${this.filePath}`);
    }
  }

  // ── 读写 ─────────────────────────────────────────────────────────────────

  load(): PortfolioFile {
    try {
      const content = readFileSync(this.filePath, "utf-8");
      const parsed = JSON.parse(content);

      // 兼容性处理：如果是旧的数组格式，自动迁移
      if (Array.isArray(parsed)) {
        console.warn("⚠️  检测到旧格式 portfolio.json（数组），自动迁移到新格式");
        const migrated: PortfolioFile = {
          holdings: parsed,
          last_updated: nowStr()
        };
        this.save(migrated);
        return migrated;
      }

      // 新格式验证
      if (!parsed.holdings || !Array.isArray(parsed.holdings)) {
        console.error("❌ portfolio.json 格式错误，期望 { holdings: [], last_updated: '' }");
        return { holdings: [], last_updated: "" };
      }

      return parsed as PortfolioFile;
    } catch (error) {
      console.error("❌ 读取 portfolio.json 失败:", error);
      return { holdings: [], last_updated: "" };
    }
  }

  private save(data: PortfolioFile): void {
    data.last_updated = nowStr();
    FileLockService.withLockSync(this.filePath, () => {
      writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
    });
  }

  // ── 录入持仓 ─────────────────────────────────────────────────────────────

  add(
    symbol: string,
    quantity: number,
    avg_cost: number,
    commission = 0,
    name = "",
    market: "A" | "HK" = "A",
    notes = "",
  ): { success: boolean; message: string; updatedHolding?: Holding } {
    if (!symbol) return { success: false, message: "symbol 不能为空", updatedHolding: undefined };
    if (quantity <= 0) return { success: false, message: "quantity 必须大于0", updatedHolding: undefined };
    if (avg_cost <= 0) return { success: false, message: "avg_cost 必须大于0", updatedHolding: undefined };

    // ✅ OPT-005: 计算实际成本（包含手续费）
    const actualCost = commission > 0
      ? roundN((avg_cost * quantity + commission) / quantity)
      : avg_cost;

    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      const idx = data.holdings.findIndex(h => h.symbol === symbol);
      if (idx >= 0) {
        // 更新现有持仓
        const h = data.holdings[idx];
        // 若数量和成本均有效，加权平均成本
        if (h.quantity > 0 && h.avg_cost > 0) {
          const totalCost = h.quantity * h.avg_cost + quantity * actualCost;
          const totalQty = h.quantity + quantity;
          data.holdings[idx] = {
            ...h,
            quantity: totalQty,
            avg_cost: roundN(totalCost / totalQty),
            name: name || h.name,
            notes: notes || h.notes,
          };
          // 直接写入，不调用 save()（避免重复加锁）
          data.last_updated = nowStr();
          writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
          return {
            success: true,
            message: `${symbol} 已加仓，新均价 ${data.holdings[idx].avg_cost}，总持股 ${totalQty} 股`,
            updatedHolding: data.holdings[idx],
          };
        } else {
          data.holdings[idx] = { ...h, quantity, avg_cost: actualCost, name: name || h.name, notes: notes || h.notes };
          data.last_updated = nowStr();
          writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
          return {
            success: true,
            message: `${symbol} 持仓已更新`,
            updatedHolding: data.holdings[idx],
          };
        }
      } else {
        const newHolding: Holding = {
          symbol, name, quantity, avg_cost: actualCost, market, notes, added_date: today(),
        };
        data.holdings.push(newHolding);
        data.last_updated = nowStr();
        writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
        return {
          success: true,
          message: `${symbol} 已录入持仓`,
          updatedHolding: newHolding,
        };
      }
    });
  }

  /**
   * 录入港股持仓（带汇率转换）
   *
   * @param symbol 港股代码（5位）
   * @param quantity 持股数量
   * @param priceHKD 港币价格
   * @param commission 手续费（人民币）
   * @param name 股票名称
   * @param notes 备注
   * @returns 操作结果
   */
  async addHKStock(
    symbol: string,
    quantity: number,
    priceHKD: number,
    commission: number = 0,
    name: string = "",
    notes: string = ""
  ): Promise<{ success: boolean; message: string; updatedHolding?: Holding }> {

    // Validation
    if (!symbol) {
      return { success: false, message: "symbol 不能为空" };
    }
    if (quantity <= 0) {
      return { success: false, message: "quantity 必须大于0" };
    }
    if (priceHKD <= 0) {
      return { success: false, message: "priceHKD 必须大于0" };
    }
    if (commission < 0) {
      return { success: false, message: "commission 不能小于0" };
    }

    // 1. Get current FX rate with error handling
    let fxRate: number;
    try {
      fxRate = await this.fxRateService.getRate("HKDCNY");
    } catch (error) {
      return {
        success: false,
        message: `获取汇率失败: ${error instanceof Error ? error.message : String(error)}`
      };
    }

    // 2. Calculate CNY cost
    // Note: Commission is in CNY and added after HKD→CNY conversion
    const totalCostHKD = priceHKD * quantity;
    const totalCostCNY = totalCostHKD * fxRate + commission;
    const avgCostCNY = roundN(totalCostCNY / quantity);

    // 3. Check for existing holding
    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      const idx = data.holdings.findIndex(h => h.symbol === symbol);

      if (idx >= 0) {
        // Add to existing position (weighted average)
        const h = data.holdings[idx];
        const existingCostHKD = h.avg_cost_hkd || 0;
        const existingQty = h.quantity;

        const totalCostHKDWeighted = existingCostHKD * existingQty + priceHKD * quantity;
        const totalCostCNYWeighted = h.avg_cost * existingQty + avgCostCNY * quantity;
        const totalQty = existingQty + quantity;

        // Weighted average costs
        const newAvgCostHKD = roundN(totalCostHKDWeighted / totalQty);
        const newAvgCostCNY = roundN(totalCostCNYWeighted / totalQty);
        // Effective FX rate derived from averaged costs (includes commission impact)
        const newAvgFxRate = roundN(newAvgCostCNY / newAvgCostHKD, 4);

        data.holdings[idx] = {
          ...h,
          quantity: totalQty,
          avg_cost: newAvgCostCNY,
          avg_cost_hkd: newAvgCostHKD,
          purchase_fx_rate: newAvgFxRate,
          name: name || h.name,
          notes: notes || h.notes,
        };

        data.last_updated = nowStr();
        writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");

        return {
          success: true,
          message: `${symbol} 已加仓，新均价 ${newAvgCostCNY.toFixed(2)} CNY (${newAvgCostHKD.toFixed(2)} HKD)`,
          updatedHolding: data.holdings[idx],
        };
      } else {
        // New position
        const newHolding: Holding = {
          symbol,
          name,
          quantity,
          avg_cost: avgCostCNY,
          avg_cost_hkd: priceHKD,
          purchase_fx_rate: fxRate,
          market: "HK",
          notes,
          added_date: today(),
        };

        data.holdings.push(newHolding);
        data.last_updated = nowStr();
        writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");

        return {
          success: true,
          message: `${symbol} 已录入持仓`,
          updatedHolding: newHolding,
        };
      }
    });
  }

  /** 直接覆盖更新（适合修正均价/数量而非加仓） */
  update(
    symbol: string,
    quantity?: number,
    avg_cost?: number,
    name?: string,
    notes?: string,
  ): { success: boolean; message: string } {
    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      const h = data.holdings.find(h => h.symbol === symbol);
      if (!h) return { success: false, message: `未找到持仓: ${symbol}` };
      if (quantity !== undefined) h.quantity = quantity;
      if (avg_cost !== undefined) h.avg_cost = avg_cost;
      if (name !== undefined) h.name = name;
      if (notes !== undefined) h.notes = notes;
      data.last_updated = nowStr();
      writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
      return { success: true, message: `${symbol} 持仓已更新` };
    });
  }

  remove(symbol: string): { success: boolean; message: string } {
    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      const before = data.holdings.length;
      data.holdings = data.holdings.filter(h => h.symbol !== symbol);
      if (data.holdings.length === before) return { success: false, message: `未找到持仓: ${symbol}` };
      data.last_updated = nowStr();
      writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
      return { success: true, message: `${symbol} 已从持仓中移除` };
    });
  }

  replaceHoldings(holdings: Holding[]): { success: boolean; message: string } {
    return FileLockService.withLockSync(this.filePath, () => {
      const normalized = holdings.map((holding) => ({
        ...holding,
        added_date: holding.added_date || today(),
      }));
      const data: PortfolioFile = { holdings: normalized, last_updated: nowStr() };
      writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
      return { success: true, message: `已覆盖为 ${normalized.length} 只持仓` };
    });
  }

  // ── 读取持仓（带行情） ─────────────────────────────────────────────────────

  async getWithPnL(): Promise<PortfolioSnapshot> {
    const data = this.load();
    const holdings = data.holdings;

    if (holdings.length === 0) {
      return { holdings: [], total_cost: 0, total_value: 0, total_pnl: 0, total_pnl_pct: 0, as_of: today() };
    }

    // 1. Get current FX rate for HK stocks
    const fxRate = await this.fxRateService.getRate("HKDCNY");

    // 2. 并行获取所有持仓实时价格（直接调用 TS 函数，避免循环依赖）
    const priceResults = await Promise.all(
      holdings.map(h =>
        (h.market === "HK" ? get_hk_stock_price(h.symbol) : get_stock_realtime_price(h.symbol))
          .then(raw => JSON.parse(raw) as Record<string, unknown>)
          .catch(() => ({} as Record<string, unknown>))
      )
    );

    return buildPortfolioSnapshotFromQuotes(holdings, priceResults, fxRate);
  }

  // ── 文本摘要（供 agent 在 bootstrap 时读取） ────────────────────────────────

  summaryText(): string {
    const data = this.load();
    if (data.holdings.length === 0) return "持仓为空";
    const lines = data.holdings.map(h =>
      `- ${h.symbol} ${h.name || ""} | ${h.quantity}股 × 均价 ${h.avg_cost} 元${h.notes ? ` | 备注: ${h.notes}` : ""}`
    );
    return `持仓 ${data.holdings.length} 只（更新: ${data.last_updated || "未知"}）：\n${lines.join("\n")}`;
  }

  /** 持仓文件路径 */
  get path(): string { return this.filePath; }

  /** 是否有持仓 */
  hasHoldings(): boolean { return this.load().holdings.length > 0; }

  // ── 高层业务方法 ────────────────────────────────────────────────────────

  /**
   * 卖出持仓（高层业务方法）
   *
   * 包含：校验持仓 → 计算盈亏 → 更新持仓 → 记录交易
   *
   * @param symbol 股票代码
   * @param quantity 卖出数量
   * @param price 卖出价格
   * @param commission 手续费（默认0）
   * @param notes 备注
   * @returns 结构化的卖出结果
   */
  sell(
    symbol: string,
    quantity: number,
    price: number,
    commission = 0,
    notes = "",
  ): SellResult {
    // 1. 校验参数
    if (!symbol) {
      throw new Error("symbol 不能为空");
    }
    if (quantity <= 0) {
      throw new Error("quantity 必须大于0");
    }
    if (price <= 0) {
      throw new Error("price 必须大于0");
    }
    if (commission < 0) {
      throw new Error("commission 不能小于0");
    }

    // 2. 校验持仓
    const holding = this.load().holdings.find(h => h.symbol === symbol);
    if (!holding) {
      throw new Error(`未找到持仓: ${symbol}`);
    }

    if (holding.quantity < quantity) {
      throw new Error(`持仓不足: 需卖出 ${quantity} 股，实际仅持有 ${holding.quantity} 股`);
    }

    // 3. 计算盈亏（扣除手续费）
    const remaining = holding.quantity - quantity;
    const grossProceeds = price * quantity;           // 卖出总收入
    const netProceeds = grossProceeds - commission;   // 扣除手续费后的净收入
    const costBasis = holding.avg_cost * quantity;    // 成本
    const pnlAmount = roundN(netProceeds - costBasis); // 实际盈亏
    const pnlPct = roundN((pnlAmount / costBasis) * 100);

    // 4. 更新持仓
    let updatedHolding: Holding | undefined;
    if (remaining <= 0) {
      this.remove(symbol);
    } else {
      this.update(symbol, remaining, holding.avg_cost, undefined, notes);
      updatedHolding = this.load().holdings.find(h => h.symbol === symbol);
    }

    // 5. 记录交易
    let tradeRecorded = false;
    if (this.tradeService) {
      try {
        this.tradeService.add(
          chinaDate(),
          symbol,
          holding.name || symbol,
          "sell",
          quantity,
          price,
          commission,
          holding.market || "A",
          notes || "卖出",
          pnlAmount,    // 传递盈亏金额
          pnlPct,       // 传递盈亏比例
        );
        tradeRecorded = true;
      } catch (e) {
        console.warn("交易记录失败:", e);
      }
    }

    // 6. 获取完整持仓快照（异步，不阻塞主流程）
    const portfolioSnapshot = this.getWithPnL().catch(() => undefined);

    return {
      success: true,
      message: `卖出 ${symbol} ${quantity}股@${price.toFixed(2)}，${remaining > 0 ? `剩余 ${remaining}股` : "已清仓"}`,
      symbol,
      sellPrice: price,
      quantity,
      remaining,
      pnlAmount,
      pnlPct,
      tradeRecorded,
      updatedHolding,
      portfolioSnapshot: undefined, // 同步返回时先不包含快照，避免阻塞
    };
  }
}
