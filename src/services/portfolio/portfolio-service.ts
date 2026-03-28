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

// ─── 数据结构 ──────────────────────────────────────────────────────────────

export interface Holding {
  symbol: string;      // 股票代码（6位A股 或 5位港股）
  name: string;        // 股票名称（可从行情更新）
  quantity: number;    // 持股数量（股）
  avg_cost: number;    // 持仓均价（元/港元）
  market: "A" | "HK";  // 市场类型
  notes: string;       // 备注（如：分批建仓批次、操作背景等）
  added_date: string;  // 首次录入日期
}

export interface PortfolioFile {
  holdings: Holding[];
  last_updated: string;
}

export interface HoldingWithPnL extends Holding {
  current_price: number;
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
): PortfolioSnapshot {
  if (holdings.length === 0) {
    return { holdings: [], total_cost: 0, total_value: 0, total_pnl: 0, total_pnl_pct: 0, as_of: today() };
  }

  let totalCost = 0;
  let totalValue = 0;

  const enriched: HoldingWithPnL[] = holdings.map((h, i) => {
    const rt = priceResults[i] ?? {};
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

  constructor(piDir: string) {
    this.filePath = join(piDir, "portfolio.json");
    mkdirSync(piDir, { recursive: true });
    this.ensureFile();
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
      return JSON.parse(readFileSync(this.filePath, "utf-8")) as PortfolioFile;
    } catch {
      return { holdings: [], last_updated: "" };
    }
  }

  private save(data: PortfolioFile): void {
    data.last_updated = nowStr();
    writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
  }

  // ── 录入持仓 ─────────────────────────────────────────────────────────────

  add(
    symbol: string,
    quantity: number,
    avg_cost: number,
    name = "",
    market: "A" | "HK" = "A",
    notes = "",
  ): { success: boolean; message: string } {
    if (!symbol) return { success: false, message: "symbol 不能为空" };
    if (quantity <= 0) return { success: false, message: "quantity 必须大于0" };
    if (avg_cost <= 0) return { success: false, message: "avg_cost 必须大于0" };

    const data = this.load();
    const idx = data.holdings.findIndex(h => h.symbol === symbol);
    if (idx >= 0) {
      // 更新现有持仓
      const h = data.holdings[idx];
      // 若数量和成本均有效，加权平均成本
      if (h.quantity > 0 && h.avg_cost > 0) {
        const totalCost = h.quantity * h.avg_cost + quantity * avg_cost;
        const totalQty = h.quantity + quantity;
        data.holdings[idx] = {
          ...h,
          quantity: totalQty,
          avg_cost: roundN(totalCost / totalQty),
          name: name || h.name,
          notes: notes || h.notes,
        };
        this.save(data);
        return { success: true, message: `${symbol} 已加仓，新均价 ${data.holdings[idx].avg_cost}，总持股 ${totalQty} 股` };
      } else {
        data.holdings[idx] = { ...h, quantity, avg_cost, name: name || h.name, notes: notes || h.notes };
        this.save(data);
        return { success: true, message: `${symbol} 持仓已更新` };
      }
    } else {
      data.holdings.push({
        symbol, name, quantity, avg_cost, market, notes, added_date: today(),
      });
      this.save(data);
      return { success: true, message: `${symbol} 已录入持仓` };
    }
  }

  /** 直接覆盖更新（适合修正均价/数量而非加仓） */
  update(
    symbol: string,
    quantity?: number,
    avg_cost?: number,
    name?: string,
    notes?: string,
  ): { success: boolean; message: string } {
    const data = this.load();
    const h = data.holdings.find(h => h.symbol === symbol);
    if (!h) return { success: false, message: `未找到持仓: ${symbol}` };
    if (quantity !== undefined) h.quantity = quantity;
    if (avg_cost !== undefined) h.avg_cost = avg_cost;
    if (name !== undefined) h.name = name;
    if (notes !== undefined) h.notes = notes;
    this.save(data);
    return { success: true, message: `${symbol} 持仓已更新` };
  }

  remove(symbol: string): { success: boolean; message: string } {
    const data = this.load();
    const before = data.holdings.length;
    data.holdings = data.holdings.filter(h => h.symbol !== symbol);
    if (data.holdings.length === before) return { success: false, message: `未找到持仓: ${symbol}` };
    this.save(data);
    return { success: true, message: `${symbol} 已从持仓中移除` };
  }

  replaceHoldings(holdings: Holding[]): { success: boolean; message: string } {
    const normalized = holdings.map((holding) => ({
      ...holding,
      added_date: holding.added_date || today(),
    }));
    this.save({ holdings: normalized, last_updated: "" });
    return { success: true, message: `已覆盖为 ${normalized.length} 只持仓` };
  }

  // ── 读取持仓（带行情） ─────────────────────────────────────────────────────

  async getWithPnL(): Promise<PortfolioSnapshot> {
    const data = this.load();
    const holdings = data.holdings;

    if (holdings.length === 0) {
      return { holdings: [], total_cost: 0, total_value: 0, total_pnl: 0, total_pnl_pct: 0, as_of: today() };
    }

    // 并行获取所有持仓实时价格（直接调用 TS 函数，避免循环依赖）
    const priceResults = await Promise.all(
      holdings.map(h =>
        (h.market === "HK" ? get_hk_stock_price(h.symbol) : get_stock_realtime_price(h.symbol))
          .then(raw => JSON.parse(raw) as Record<string, unknown>)
          .catch(() => ({} as Record<string, unknown>))
      )
    );

    return buildPortfolioSnapshotFromQuotes(holdings, priceResults);
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
}
