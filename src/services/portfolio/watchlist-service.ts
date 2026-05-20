/**
 * WatchlistService — 关注股票列表管理服务
 *
 * 管理"想买的股票"备选池，独立于已持仓管理。
 * 数据存储在 .pi-invest/watchlist.json
 *
 * 关注列表分四个状态：
 *   - watching: 观察中，尚未到买入区间
 *   - ready: 价格已达目标区间，可以买入
 *   - bought: 已买入，移入持仓
 *   - discarded: 已放弃关注
 *
 * 三个池子：
 *   A池=核心建仓（确定性高，随时准备出手）
 *   B池=候选观察（需要等买点或更多确认）
 *   C池=研究关注（初步了解，待深度分析）
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { chinaDate, chinaDateTime } from '../../utils/china-time.js';

// ── WatchlistItem 类型 ────────────────────────────────────────────────────
export interface WatchlistItem {
  symbol: string;
  name: string;
  market: string;
  buy_range_low: number;
  buy_range_high: number;
  target_price: number;
  stop_loss: number;
  priority: number;
  pool: 'A' | 'B' | 'C';
  status: 'watching' | 'ready' | 'bought' | 'discarded';
  reason: string;
  notes: string;
  created_at: string;
  updated_at: string;
  [key: string]: any; // 允许额外字段
}

interface WatchlistData {
  items: WatchlistItem[];
  last_updated: string;
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

// ─── WatchlistService ──────────────────────────────────────────────────────
export class WatchlistService {
  private filePath: string;

  constructor(piDir: string) {
    this.filePath = join(piDir, 'watchlist.json');
    mkdirSync(piDir, { recursive: true });
    this.ensureFile();
  }

  // ── 文件初始化 ────────────────────────────────────────────────────────────
  private ensureFile(): void {
    if (!existsSync(this.filePath)) {
      const empty: WatchlistData = { items: [], last_updated: '' };
      writeFileSync(this.filePath, JSON.stringify(empty, null, 2), 'utf-8');
      console.log(`[watchlist] 初始化关注列表文件: ${this.filePath}`);
    }
  }

  // ── 读写 ─────────────────────────────────────────────────────────────────
  private load(): WatchlistData {
    try {
      return JSON.parse(readFileSync(this.filePath, 'utf-8'));
    } catch {
      return { items: [], last_updated: '' };
    }
  }

  private save(data: WatchlistData): void {
    data.last_updated = nowStr();
    writeFileSync(this.filePath, JSON.stringify(data, null, 2), 'utf-8');
  }

  // ── 查询 ─────────────────────────────────────────────────────────────────

  /** 按代码查询 */
  get(symbol: string): WatchlistItem | undefined {
    return this.load().items.find((i) => i.symbol === symbol);
  }

  /** 按状态查询 */
  getByStatus(status: string): WatchlistItem[] {
    return this.load().items.filter((i) => i.status === status);
  }

  /** 按池查询 */
  getByPool(pool: string): WatchlistItem[] {
    return this.load().items.filter(
      (i) => i.pool === pool && i.status !== 'discarded' && i.status !== 'bought'
    );
  }

  /** 获取 Ready（可以买入）列表 */
  getReadyToBuy(): WatchlistItem[] {
    return this.load().items.filter((i) => i.status === 'ready');
  }

  /** 获取完整摘要（按池分类） */
  getSummary(): Record<string, any> {
    const data = this.load();
    const all = data.items;
    return {
      A_pool: all.filter(
        (i) => (i.pool === 'A' && i.status === 'watching') || i.status === 'ready'
      ),
      B_pool: all.filter(
        (i) => (i.pool === 'B' && i.status === 'watching') || i.status === 'ready'
      ),
      C_pool: all.filter(
        (i) => (i.pool === 'C' && i.status === 'watching') || i.status === 'ready'
      ),
      bought: all.filter((i) => i.status === 'bought'),
      discarded: all.filter((i) => i.status === 'discarded'),
      total: all.length,
    };
  }

  // ── 增删改 ───────────────────────────────────────────────────────────────

  /**
   * 添加关注股票
   */
  add(
    symbol: string,
    name: string,
    market: string,
    reason: string,
    buy_range_low: number,
    buy_range_high = 0,
    target_price = 0,
    stop_loss = 0,
    priority = 3,
    pool: 'A' | 'B' | 'C' = 'C',
    notes = ''
  ): { success: boolean; message?: string; error?: string } {
    if (!symbol) return { success: false, message: 'symbol 不能为空' };

    const data = this.load();
    const existing = data.items.find((i) => i.symbol === symbol);

    if (existing) {
      if (existing.status === 'bought') {
        return {
          success: false,
          message: `${symbol} ${name} 已标记为已买入，请使用 update 修改`,
        };
      }
      if (existing.status === 'discarded') {
        // 重新关注
        existing.status = 'watching';
        existing.buy_range_low = buy_range_low;
        existing.buy_range_high = buy_range_high;
        existing.target_price = target_price;
        existing.stop_loss = stop_loss;
        existing.priority = priority;
        existing.pool = pool;
        existing.reason = reason;
        existing.notes = notes;
        existing.updated_at = nowStr();
        this.save(data);
        return { success: true, message: `${symbol} ${name} 已重新加入关注列表（之前已放弃）` };
      }

      return {
        success: false,
        message: `${symbol} ${name} 已在关注列表中（状态: ${existing.status}），请使用 update 修改`,
      };
    }

    data.items.push({
      symbol,
      name,
      market,
      buy_range_low,
      buy_range_high,
      target_price,
      stop_loss,
      priority,
      pool,
      status: 'watching',
      reason,
      notes,
      created_at: nowStr(),
      updated_at: nowStr(),
    });

    this.save(data);
    return {
      success: true,
      message: `${symbol} ${name} 已加入关注列表（${pool}池，优先级${priority}）`,
    };
  }

  /**
   * 更新关注股票信息
   */
  update(
    symbol: string,
    updates: Partial<WatchlistItem>
  ): { success: boolean; message?: string; error?: string } {
    const data = this.load();
    const item = data.items.find((i) => i.symbol === symbol);
    if (!item) return { success: false, message: `未在关注列表中找到: ${symbol}` };

    Object.assign(item, updates, { updated_at: nowStr() });
    this.save(data);
    return { success: true, message: `${symbol} ${item.name} 已更新` };
  }

  /**
   * 从关注列表中移除
   */
  remove(symbol: string): { success: boolean; message?: string; error?: string } {
    const data = this.load();
    const idx = data.items.findIndex((i) => i.symbol === symbol);
    if (idx < 0) return { success: false, message: `未在关注列表中找到: ${symbol}` };

    const item = data.items[idx];
    data.items.splice(idx, 1);
    this.save(data);
    return { success: true, message: `${symbol} ${item.name} 已从关注列表中移除` };
  }

  /**
   * 标记为已买入（移入持仓后调用）
   */
  markAsBought(symbol: string, notes = ''): { success: boolean; message?: string; error?: string } {
    const data = this.load();
    const item = data.items.find((i) => i.symbol === symbol);
    if (!item) return { success: false, message: `未在关注列表中找到: ${symbol}` };

    item.status = 'bought';
    item.notes = notes || item.notes;
    item.updated_at = nowStr();
    this.save(data);
    return { success: true, message: `${symbol} ${item.name} 已标记为已买入` };
  }

  /**
   * 标记为已放弃
   */
  markAsDiscarded(symbol: string, reason = ''): { success: boolean; message?: string; error?: string } {
    const data = this.load();
    const item = data.items.find((i) => i.symbol === symbol);
    if (!item) return { success: false, message: `未在关注列表中找到: ${symbol}` };

    item.status = 'discarded';
    item.notes = reason ? `[已放弃] ${reason}` : item.notes;
    item.updated_at = nowStr();
    this.save(data);
    return { success: true, message: `${symbol} ${item.name} 已标记为已放弃` };
  }

  // ── 文本摘要 ───────────────────────────────────────────────────────────────
  summaryText(): string {
    const summary = this.getSummary();
    const lines: string[] = [];

    if (summary.A_pool.length > 0) {
      lines.push('【A池·核心建仓】');
      summary.A_pool.forEach((i: WatchlistItem) => {
        lines.push(
          `  ${i.symbol} ${i.name} | 买入区间 ¥${i.buy_range_low}~${i.buy_range_high || '市价'} | 目标 ¥${i.target_price} | 止损 ¥${i.stop_loss} | ${i.reason.substring(0, 40)}`
        );
      });
    }

    if (summary.B_pool.length > 0) {
      lines.push('【B池·候选观察】');
      summary.B_pool.forEach((i: WatchlistItem) => {
        lines.push(
          `  ${i.symbol} ${i.name} | 买入区间 ¥${i.buy_range_low}~${i.buy_range_high || '市价'} | 目标 ¥${i.target_price} | ${i.reason.substring(0, 40)}`
        );
      });
    }

    if (summary.C_pool.length > 0) {
      lines.push('【C池·研究关注】');
      summary.C_pool.forEach((i: WatchlistItem) => {
        lines.push(
          `  ${i.symbol} ${i.name} | 买入区间 ¥${i.buy_range_low}~${i.buy_range_high || '市价'} | ${i.reason.substring(0, 40)}`
        );
      });
    }

    lines.push(`\n共 ${summary.total} 只（A池${summary.A_pool.length} / B池${summary.B_pool.length} / C池${summary.C_pool.length}）`);

    const readyItems = this.getReadyToBuy();
    if (readyItems.length > 0) {
      lines.push(
        `\n⚠️ 当前可买入：${readyItems.map((i) => `${i.name}(¥${i.buy_range_low}~${i.buy_range_high || '市价'})`).join('、')}`
      );
    }

    return lines.join('\n');
  }

  /** 文件路径 */
  get path(): string {
    return this.filePath;
  }
}
