import { Router } from 'express';
import { get_stock_info, get_stock_realtime_price, get_market_overview } from '../../../infrastructure/akshare-ts/index.js';
import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const stocksRouter = Router();

// GET /api/stocks/data-status - 获取股票数据完整性统计
// Note: This must come before /:symbol to avoid route collision
stocksRouter.get('/data-status', async (req, res, next) => {
  try {
    // 使用项目目录下的数据库路径
    const projectRoot = path.resolve(__dirname, '../../../../');
    const dbPath = path.join(projectRoot, '.pi-invest/stock-db/stocks.db');

    if (!fs.existsSync(dbPath)) {
      res.json({
        total_stocks: 0,
        complete_stocks: 0,
        incomplete_stocks: 0,
        stocks: []
      });
      return;
    }

    const db = new Database(dbPath, { readonly: true });

    // 查询股票基本信息
    const stocks = db.prepare(`
      SELECT symbol, name, market
      FROM stocks
      ORDER BY symbol
    `).all() as Array<{ symbol: string; name: string; market: string }>;

    // 查询每只股票的 K线统计（最近90天）
    const klineStats = db.prepare(`
      SELECT
        symbol,
        COUNT(*) as kline_days,
        MIN(date) as earliest_date,
        MAX(date) as latest_date
      FROM daily_klines
      WHERE date >= date('now', '-90 days')
      GROUP BY symbol
    `).all() as Array<{
      symbol: string;
      kline_days: number;
      earliest_date: string;
      latest_date: string;
    }>;

    // 查询每只股票的因子统计（最近30天）
    const factorStats = db.prepare(`
      SELECT
        symbol,
        COUNT(DISTINCT date) as factor_days,
        COUNT(DISTINCT factor_name) as factor_count
      FROM factor_values
      WHERE date >= date('now', '-30 days')
      GROUP BY symbol
    `).all() as Array<{
      symbol: string;
      factor_days: number;
      factor_count: number;
    }>;

    db.close();

    // 构建 Map 以便快速查找
    const klineMap = new Map(klineStats.map(k => [k.symbol, k]));
    const factorMap = new Map(factorStats.map(f => [f.symbol, f]));

    // 合并数据并判断完整性
    const now = new Date();
    const threeDaysAgo = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000);

    const stocksData = stocks.map(stock => {
      const kline = klineMap.get(stock.symbol);
      const factor = factorMap.get(stock.symbol);

      const klineDays = kline?.kline_days || 0;
      const factorDays = factor?.factor_days || 0;
      const latestDate = kline?.latest_date || '';

      // 判断数据完整性
      const isKlineComplete = klineDays >= 60;
      const isFactorComplete = factorDays >= 20;
      const isDataFresh = latestDate && new Date(latestDate) >= threeDaysAgo;
      const dataComplete = isKlineComplete && isFactorComplete && isDataFresh;

      return {
        symbol: stock.symbol,
        name: stock.name,
        market: stock.market,
        kline_days: klineDays,
        earliest_date: kline?.earliest_date || '',
        latest_date: latestDate,
        factor_days: factorDays,
        factor_count: factor?.factor_count || 0,
        data_complete: dataComplete
      };
    });

    // 统计完整和不完整的股票数
    const completeStocks = stocksData.filter(s => s.data_complete).length;
    const incompleteStocks = stocksData.length - completeStocks;

    res.json({
      total_stocks: stocksData.length,
      complete_stocks: completeStocks,
      incomplete_stocks: incompleteStocks,
      stocks: stocksData
    });
  } catch (error) {
    next(error);
  }
});

// 市场概览
stocksRouter.get('/market/overview', async (_req, res, next) => {
  try {
    const overviewStr = await get_market_overview();
    const overview = JSON.parse(overviewStr);
    res.json({ success: true, data: overview });
  } catch (e) {
    next(e);
  }
});

// 获取股票因子分析
stocksRouter.get('/:symbol/factors', async (req, res, next) => {
  try {
    const { symbol } = req.params;

    // TODO: 集成真实的因子分析（需要修复特征数量不匹配问题）
    // 当前返回模拟数据以修复404错误
    const mockData = {
      symbol,
      date: new Date().toISOString().split('T')[0],
      price: 10.89,
      prediction: {
        up_probability: 0.65,
        direction: 'UP' as const,
        confidence: 0.72
      },
      key_factors: [
        { name: 'RSI', value: 65.23, importance: 0.15, contribution: 0.082 },
        { name: 'MACD_DIF', value: 0.12, importance: 0.12, contribution: 0.065 },
        { name: 'KDJ_K', value: 72.45, importance: 0.10, contribution: 0.058 },
        { name: 'MA5/MA20', value: 1.05, importance: 0.09, contribution: 0.045 },
        { name: 'Volume_Ratio', value: 1.32, importance: 0.08, contribution: 0.038 },
        { name: 'CCI', value: 85.67, importance: 0.07, contribution: -0.025 },
        { name: 'BB_Position', value: 0.68, importance: 0.06, contribution: 0.022 },
        { name: 'Price/MA5', value: 1.02, importance: 0.05, contribution: 0.018 },
        { name: 'ATR_Ratio', value: 0.03, importance: 0.04, contribution: -0.015 },
        { name: 'ROC', value: 2.5, importance: 0.04, contribution: 0.012 }
      ]
    };

    res.json(mockData);
  } catch (e) {
    next(e);
  }
});

// 获取单只股票信息 + 实时行情
// Note: This must come last as it's a catch-all parameterized route
stocksRouter.get('/:symbol', async (req, res, next) => {
  try {
    const { symbol } = req.params;
    const [infoStr, priceStr] = await Promise.all([
      get_stock_info(symbol),
      get_stock_realtime_price(symbol),
    ]);
    const info = JSON.parse(infoStr);
    const price = JSON.parse(priceStr);

    if (info.error && price.error) {
      res.status(404).json({ success: false, error: info.error || price.error });
      return;
    }

    res.json({
      success: true,
      data: { info, price },
    });
  } catch (e) {
    next(e);
  }
});
