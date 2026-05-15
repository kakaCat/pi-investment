/**
 * TradeService — 交易历史管理
 *
 * 存储路径: .pi-invest/trades.json
 * 每条交易记录买入/卖出，记录后可重建持仓快照。
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { chinaDateTime } from "../../utils/china-time.js";

// ─── 数据结构 ──────────────────────────────────────────────────────────────

export type TradeAction = "buy" | "sell";

export interface Trade {
  id: string;
  date: string;          // YYYY-MM-DD
  symbol: string;
  name: string;
  action: TradeAction;
  quantity: number;      // 股数
  price: number;         // 成交均价（元/港元）
  commission: number;    // 手续费（元）
  amount: number;        // 成交金额 = quantity × price（不含手续费）
  market: "A" | "HK";
  notes: string;
}

export interface TradesFile {
  trades: Trade[];
  last_updated: string;
}

// ─── 工具函数 ──────────────────────────────────────────────────────────────

function makeId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

function nowStr(): string {
  return chinaDateTime();
}

function roundN(v: number, n = 2): number {
  return Math.round(v * Math.pow(10, n)) / Math.pow(10, n);
}

// ─── TradeService ──────────────────────────────────────────────────────────

export class TradeService {
  private filePath: string;

  constructor(piDir: string) {
    this.filePath = join(piDir, "trades.json");
    mkdirSync(piDir, { recursive: true });
    this.ensureFile();
  }

  private ensureFile(): void {
    if (!existsSync(this.filePath)) {
      writeFileSync(this.filePath, JSON.stringify({ trades: [], last_updated: "" }, null, 2), "utf-8");
    }
  }

  load(): TradesFile {
    try {
      const content = readFileSync(this.filePath, "utf-8");
      const parsed = JSON.parse(content);

      // 兼容性处理：如果是旧的数组格式，自动迁移
      if (Array.isArray(parsed)) {
        console.warn("⚠️  检测到旧格式 trades.json（数组），自动迁移到新格式");
        const migrated: TradesFile = {
          trades: parsed,
          last_updated: nowStr()
        };
        this.save(migrated);
        return migrated;
      }

      // 新格式验证
      if (!parsed.trades || !Array.isArray(parsed.trades)) {
        console.error("❌ trades.json 格式错误，期望 { trades: [], last_updated: '' }");
        return { trades: [], last_updated: "" };
      }

      return parsed as TradesFile;
    } catch (error) {
      console.error("❌ 读取 trades.json 失败:", error);
      return { trades: [], last_updated: "" };
    }
  }

  private save(data: TradesFile): void {
    data.last_updated = nowStr();
    writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
  }

  // ── 录入交易 ────────────────────────────────────────────────────────────

  add(
    date: string,
    symbol: string,
    name: string,
    action: TradeAction,
    quantity: number,
    price: number,
    commission = 0,
    market: "A" | "HK" = "A",
    notes = "",
  ): Trade {
    if (quantity <= 0) throw new Error("quantity 必须大于0");
    if (price <= 0) throw new Error("price 必须大于0");
    if (commission < 0) throw new Error("commission 不能小于0");

    if (action === "sell") {
      const openQty = this.buildSnapshot().get(symbol)?.quantity ?? 0;
      if (openQty < quantity) {
        throw new Error(`卖出数量超过当前持仓: ${symbol} 持仓 ${openQty} 股，尝试卖出 ${quantity} 股`);
      }
    }

    const trade: Trade = {
      id: makeId(),
      date, symbol, name, action, quantity, price,
      commission: roundN(commission),
      amount: roundN(quantity * price),
      market, notes,
    };
    const data = this.load();
    data.trades.push(trade);
    // 按日期排序
    data.trades.sort((a, b) => a.date.localeCompare(b.date));
    this.save(data);
    return trade;
  }

  remove(id: string): boolean {
    const data = this.load();
    const before = data.trades.length;
    data.trades = data.trades.filter(t => t.id !== id);
    if (data.trades.length === before) return false;
    this.save(data);
    return true;
  }

  // ── 查询 ────────────────────────────────────────────────────────────────

  bySymbol(symbol: string): Trade[] {
    return this.load().trades.filter(t => t.symbol === symbol);
  }

  recent(limit = 20): Trade[] {
    const all = this.load().trades;
    return all.slice(-limit).reverse();
  }

  // ── 从交易记录重建持仓快照 ───────────────────────────────────────────────

  buildSnapshot(): Map<string, { symbol: string; name: string; quantity: number; avg_cost: number; market: "A" | "HK"; realized_pnl: number }> {
    const map = new Map<string, { symbol: string; name: string; quantity: number; avg_cost: number; market: "A" | "HK"; realized_pnl: number; total_cost: number }>();

    for (const t of this.load().trades) {
      const prev = map.get(t.symbol) ?? { symbol: t.symbol, name: t.name, quantity: 0, avg_cost: 0, market: t.market, realized_pnl: 0, total_cost: 0 };

      if (t.action === "buy") {
        const newTotalCost = prev.total_cost + t.amount + t.commission;
        const newQty = prev.quantity + t.quantity;
        map.set(t.symbol, {
          ...prev,
          name: t.name || prev.name,
          quantity: newQty,
          avg_cost: newQty > 0 ? roundN(newTotalCost / newQty) : 0,
          total_cost: newTotalCost,
        });
      } else {
        // sell — realize P&L
        if (prev.quantity < t.quantity) {
          throw new Error(`交易历史存在超卖: ${t.symbol} 在 ${t.date} 尝试卖出 ${t.quantity} 股，但当时仅持有 ${prev.quantity} 股`);
        }
        const sellAmt = t.amount - t.commission;
        const costBasis = prev.avg_cost * t.quantity;
        const realizedPnl = sellAmt - costBasis;
        const newQty = prev.quantity - t.quantity;
        const newTotalCost = prev.total_cost - costBasis;
        map.set(t.symbol, {
          ...prev,
          quantity: newQty,
          avg_cost: newQty > 0 ? roundN(newTotalCost / newQty) : 0,
          total_cost: newQty > 0 ? roundN(newTotalCost) : 0,
          realized_pnl: prev.realized_pnl + realizedPnl,
        });
      }
    }

    // 过滤已清仓
    for (const [sym, pos] of map) {
      if (pos.quantity <= 0) map.delete(sym);
    }

    return map;
  }

  // ── 统计摘要 ────────────────────────────────────────────────────────────

  summary(): { total: number; buys: number; sells: number; symbols: number; totalBuyAmount: number; totalSellAmount: number } {
    const trades = this.load().trades;
    const buys = trades.filter(t => t.action === "buy");
    const sells = trades.filter(t => t.action === "sell");
    return {
      total: trades.length,
      buys: buys.length,
      sells: sells.length,
      symbols: new Set(trades.map(t => t.symbol)).size,
      totalBuyAmount: roundN(buys.reduce((s, t) => s + t.amount + t.commission, 0)),
      totalSellAmount: roundN(sells.reduce((s, t) => s + t.amount - t.commission, 0)),
    };
  }
}
