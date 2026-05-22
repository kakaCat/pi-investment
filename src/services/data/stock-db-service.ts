/**
 * StockDBService - 本地股票数据库
 *
 * 功能：
 * 1. 初始化数据库
 * 2. 更新股票列表
 * 3. 快速筛选股票池
 */

import Database from 'better-sqlite3';
import { join } from 'path';
import { mkdirSync } from 'fs';
import { callQuantSysDaemon } from '../../infrastructure/quant/quantsys-daemon-adapter.js';

export interface StockFilter {
  market?: 'A' | 'HK';
  industry?: string;
  min_market_cap?: number;
  max_market_cap?: number;
  min_pe?: number;
  max_pe?: number;
  min_pb?: number;
  max_pb?: number;
  exclude_st?: boolean;
  exclude_suspended?: boolean;
  min_daily_amount?: number;  // 最小日均成交额（万元）
  list_days?: number;          // 上市天数
}

export interface StockInfo {
  symbol: string;
  name: string;
  market: string;
  industry?: string;
  market_cap?: number;
  pe?: number;
  pb?: number;
}

export interface KlineCoverage {
  existing_days: number;
  first_date: string | null;
  last_date: string | null;
}

export class StockDBService {
  private static instances: Map<string, StockDBService> = new Map();
  private db: Database.Database;
  private dbPath: string;

  private constructor(piDir: string) {
    const dbDir = join(piDir, 'stock-db');
    mkdirSync(dbDir, { recursive: true });
    this.dbPath = join(dbDir, 'stocks.db');
    this.db = new Database(this.dbPath, {
      timeout: 5000,
      fileMustExist: false
    });
    // Enable WAL mode for better concurrent access
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('busy_timeout = 5000');
    this.initDB();
  }

  public static getInstance(piDir: string): StockDBService {
    if (!StockDBService.instances.has(piDir)) {
      StockDBService.instances.set(piDir, new StockDBService(piDir));
    }
    return StockDBService.instances.get(piDir)!;
  }

  private initDB(): void {
    // 创建表
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS stocks (
        symbol TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        market TEXT NOT NULL,
        industry TEXT,
        market_cap REAL,
        pe REAL,
        pb REAL,
        roe REAL,
        gross_margin REAL,
        debt_ratio REAL,
        total_mv REAL,
        circulating_mv REAL,
        is_st INTEGER DEFAULT 0,
        is_suspended INTEGER DEFAULT 0,
        list_date TEXT,
        updated_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS daily_quotes (
        symbol TEXT NOT NULL,
        date TEXT NOT NULL,
        close REAL,
        volume REAL,
        amount REAL,
        turnover_rate REAL,
        PRIMARY KEY (symbol, date)
      );

      CREATE INDEX IF NOT EXISTS idx_market ON stocks(market);
      CREATE INDEX IF NOT EXISTS idx_industry ON stocks(industry);
      CREATE INDEX IF NOT EXISTS idx_market_cap ON stocks(market_cap);
      CREATE INDEX IF NOT EXISTS idx_pe ON stocks(pe);

      CREATE TABLE IF NOT EXISTS daily_klines (
        symbol TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        amount REAL,
        PRIMARY KEY (symbol, date)
      );

      CREATE INDEX IF NOT EXISTS idx_kline_symbol ON daily_klines(symbol);
      CREATE INDEX IF NOT EXISTS idx_kline_date ON daily_klines(date);
    `);
  }

  /** 更新 A 股列表 */
  async updateAStocks(): Promise<number> {
    console.log('[StockDB] 更新 A 股列表...');
    const raw = await callQuantSysDaemon("get_stock_list", { market: "A" });
    const data = JSON.parse(raw);

    if (!Array.isArray(data.stocks)) return 0;

    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO stocks
      (symbol, name, market, industry, market_cap, pe, pb, roe, gross_margin, debt_ratio, is_st, list_date, updated_at)
      VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    `);

    const insert = this.db.transaction((stocks: any[]) => {
      for (const s of stocks) {
        const isST = s.name?.includes('ST') || s.name?.includes('*') ? 1 : 0;
        stmt.run(
          s.code || s.symbol,
          s.name,
          s.industry || null,
          s.market_cap || s.total_mv || null,
          s.pe || null,
          s.pb || null,
          s.roe || null,
          s.gross_margin || null,
          s.debt_ratio || null,
          isST,
          s.list_date || null
        );
      }
    });

    insert(data.stocks);
    console.log(`[StockDB] A 股更新完成：${data.stocks.length} 只`);
    return data.stocks.length;
  }

  /** 筛选股票池 */
  filter(filters: StockFilter): StockInfo[] {
    let sql = 'SELECT symbol, name, market, industry, market_cap, pe, pb FROM stocks WHERE 1=1';
    const params: any[] = [];

    if (filters.market) {
      sql += ' AND market = ?';
      params.push(filters.market);
    }

    if (filters.industry) {
      sql += ' AND industry = ?';
      params.push(filters.industry);
    }

    if (filters.min_market_cap) {
      sql += ' AND market_cap >= ?';
      params.push(filters.min_market_cap);
    }

    if (filters.max_market_cap) {
      sql += ' AND market_cap <= ?';
      params.push(filters.max_market_cap);
    }

    if (filters.min_pe) {
      sql += ' AND pe >= ?';
      params.push(filters.min_pe);
    }

    if (filters.max_pe) {
      sql += ' AND pe <= ? AND pe > 0';
      params.push(filters.max_pe);
    }

    if (filters.min_pb) {
      sql += ' AND pb >= ?';
      params.push(filters.min_pb);
    }

    if (filters.max_pb) {
      sql += ' AND pb <= ? AND pb > 0';
      params.push(filters.max_pb);
    }

    if (filters.exclude_st) {
      sql += ' AND is_st = 0';
    }

    if (filters.exclude_suspended) {
      sql += ' AND is_suspended = 0';
    }

    if (filters.list_days) {
      sql += ` AND julianday('now') - julianday(list_date) >= ?`;
      params.push(filters.list_days);
    }

    return this.db.prepare(sql).all(...params) as StockInfo[];
  }

  /** 获取股票总数 */
  count(market?: 'A' | 'HK'): number {
    if (market) {
      return (this.db.prepare('SELECT COUNT(*) as cnt FROM stocks WHERE market = ?').get(market) as any).cnt;
    }
    return (this.db.prepare('SELECT COUNT(*) as cnt FROM stocks').get() as any).cnt;
  }

  getStock(symbol: string): StockInfo | null {
    const row = this.db.prepare(
      'SELECT symbol, name, market, industry, market_cap, pe, pb FROM stocks WHERE symbol = ?'
    ).get(normalizeStockSymbol(symbol)) as StockInfo | undefined;
    return row || null;
  }

  upsertStocks(stocks: Array<Record<string, unknown>>): number {
    if (stocks.length === 0) {
      return 0;
    }

    const stmt = this.db.prepare(`
      INSERT INTO stocks
      (symbol, name, market, industry, market_cap, pe, pb, total_mv, circulating_mv, is_st, is_suspended, list_date, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(symbol) DO UPDATE SET
        name = excluded.name,
        market = excluded.market,
        industry = COALESCE(excluded.industry, stocks.industry),
        market_cap = COALESCE(excluded.market_cap, stocks.market_cap),
        pe = COALESCE(excluded.pe, stocks.pe),
        pb = COALESCE(excluded.pb, stocks.pb),
        total_mv = COALESCE(excluded.total_mv, stocks.total_mv),
        circulating_mv = COALESCE(excluded.circulating_mv, stocks.circulating_mv),
        is_st = excluded.is_st,
        is_suspended = excluded.is_suspended,
        list_date = COALESCE(excluded.list_date, stocks.list_date),
        updated_at = excluded.updated_at
    `);

    const insert = this.db.transaction((rows: Array<Record<string, unknown>>) => {
      for (const stock of rows) {
        const symbol = normalizeStockSymbol(String(stock.symbol || ''));
        if (!symbol) {
          continue;
        }
        const name = String(stock.name || symbol);
        stmt.run(
          symbol,
          name,
          String(stock.market || 'A'),
          stock.industry || stock.sector || null,
          stock.market_cap ?? null,
          stock.pe ?? stock.pe_ttm ?? null,
          stock.pb ?? null,
          stock.total_mv ?? stock.market_cap ?? null,
          stock.circulating_mv ?? null,
          stock.is_st === true || name.toUpperCase().includes('ST') ? 1 : 0,
          stock.is_suspended === true ? 1 : 0,
          stock.list_date || stock.listed_date || null,
          String(stock.updated_at || new Date().toISOString())
        );
      }
    });

    insert(stocks);
    return stocks.length;
  }

  getKlineCoverage(symbol: string): KlineCoverage {
    const row = this.db.prepare(`
      SELECT COUNT(*) as existing_days, MIN(date) as first_date, MAX(date) as last_date
      FROM daily_klines
      WHERE symbol = ?
    `).get(normalizeStockSymbol(symbol)) as KlineCoverage | undefined;

    return {
      existing_days: Number(row?.existing_days || 0),
      first_date: row?.first_date || null,
      last_date: row?.last_date || null,
    };
  }

  /** 保存K线数据 */
  saveKlines(symbol: string, klines: any[]): number {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO daily_klines
      (symbol, date, open, high, low, close, volume, amount)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const insert = this.db.transaction((data: any[]) => {
      for (const k of data) {
        stmt.run(
          symbol,
          k.date || k.日期,
          k.open || k.开盘 || null,
          k.high || k.最高 || null,
          k.low || k.最低 || null,
          k.close || k.收盘 || null,
          k.volume || k.成交量 || null,
          k.amount || k.成交额 || null
        );
      }
    });

    insert(klines);
    return klines.length;
  }

  /** 获取K线数据（自动标准化日期，兼容 DB 中 YYYYMMDD 和 YYYY-MM-DD 两种格式） */
  getKlines(symbol: string, startDate?: string, endDate?: string): any[] {
    let sql = 'SELECT * FROM daily_klines WHERE symbol = ?';
    const params: any[] = [symbol];

    if (startDate) {
      const normalized = startDate.replace(/-/g, '');
      // DB 中可能存在 YYYYMMDD 和 YYYY-MM-DD 两种格式，统一用 REPLACE 比对
      sql += ` AND REPLACE(date, '-', '') >= ?`;
      params.push(normalized);
    }

    if (endDate) {
      const normalized = endDate.replace(/-/g, '');
      sql += ` AND REPLACE(date, '-', '') <= ?`;
      params.push(normalized);
    }

    sql += ' ORDER BY date ASC';
    return this.db.prepare(sql).all(...params);
  }

  /** 按市值降序取前N只A股 */
  getTopNByMarketCap(n: number, excludeST: boolean = true): StockInfo[] {
    let sql = 'SELECT symbol, name, market, industry, market_cap, pe, pb FROM stocks WHERE market = ?';
    const params: any[] = ['A'];

    if (excludeST) {
      sql += ' AND is_st = 0';
    }

    sql += ' ORDER BY market_cap DESC LIMIT ?';
    params.push(n);

    return this.db.prepare(sql).all(...params) as StockInfo[];
  }

  /** 获取最新K线日期 */
  getLatestKlineDate(symbol: string): string | null {
    const row = this.db.prepare(
      'SELECT MAX(date) as latest FROM daily_klines WHERE symbol = ?'
    ).get(symbol) as any;
    return row?.latest || null;
  }

  /** 获取个股基本面数据（PE/PB/ROE等），用于回测 */
  getStockBasics(symbol: string): { pe: number; pb: number; roe: number; gross_margin: number; debt_ratio: number } | null {
    const row = this.db.prepare(
      'SELECT pe, pb, roe, gross_margin, debt_ratio FROM stocks WHERE symbol = ?'
    ).get(symbol) as any;
    return row || null;
  }

  close(): void {
    this.db.close();
  }
}

function normalizeStockSymbol(symbol: string): string {
  return symbol.trim().replace(/^(sh|sz|bj)/i, '').replace(/\.(SH|SZ|BJ|HK)$/i, '');
}
