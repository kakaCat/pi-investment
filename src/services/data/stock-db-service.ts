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
import { existsSync, mkdirSync } from 'fs';
import { callPython } from '../../infrastructure/tools/invest-tools.js';

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

export class StockDBService {
  private db: Database.Database;
  private dbPath: string;

  constructor(piDir: string) {
    const dbDir = join(piDir, 'stock-db');
    mkdirSync(dbDir, { recursive: true });
    this.dbPath = join(dbDir, 'stocks.db');
    this.db = new Database(this.dbPath);
    this.initDB();
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
    const raw = await callPython('get_stock_list', { market: 'A' });
    const data = JSON.parse(raw);

    if (!Array.isArray(data.stocks)) return 0;

    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO stocks
      (symbol, name, market, industry, market_cap, pe, pb, is_st, list_date, updated_at)
      VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, datetime('now'))
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

  /** 获取K线数据 */
  getKlines(symbol: string, startDate?: string, endDate?: string): any[] {
    let sql = 'SELECT * FROM daily_klines WHERE symbol = ?';
    const params: any[] = [symbol];

    if (startDate) {
      sql += ' AND date >= ?';
      params.push(startDate);
    }

    if (endDate) {
      sql += ' AND date <= ?';
      params.push(endDate);
    }

    sql += ' ORDER BY date ASC';
    return this.db.prepare(sql).all(...params);
  }

  /** 获取最新K线日期 */
  getLatestKlineDate(symbol: string): string | null {
    const row = this.db.prepare(
      'SELECT MAX(date) as latest FROM daily_klines WHERE symbol = ?'
    ).get(symbol) as any;
    return row?.latest || null;
  }

  close(): void {
    this.db.close();
  }
}
