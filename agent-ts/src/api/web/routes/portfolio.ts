/**
 * Portfolio API - 投资组合管理接口
 */
import { Router } from 'express';
import type { Request, Response } from 'express';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

const router = Router();

/**
 * 获取投资组合概览
 * GET /api/portfolio
 */
router.get('/', async (req: Request, res: Response) => {
  try {
    // TODO(P1): 旧账本 portfolio.json 已于 2026-07-19 归档（.pi-invest/archive/），
    // 此路由应迁移到 v2 simulation API (http://127.0.0.1:5001/api/simulation/accounts/default)
    // 作为唯一账本来源。当前文件缺失时降级返回空数据。
    const piDir = join(process.cwd(), '.pi-invest');
    const portfolioPath = join(piDir, 'portfolio.json');

    if (!existsSync(portfolioPath)) {
      return res.json({
        success: true,
        data: {
          holdings: [],
          total_value: 0,
          total_cost: 0,
          total_pnl: 0,
          total_pnl_pct: 0,
          cash: 0,
          last_updated: new Date().toISOString()
        }
      });
    }

    const portfolio = JSON.parse(readFileSync(portfolioPath, 'utf-8'));

    res.json({
      success: true,
      data: portfolio
    });
  } catch (error) {
    console.error('[Portfolio API] Error fetching portfolio:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * 获取持仓列表
 * GET /api/portfolio/holdings
 */
router.get('/holdings', async (req: Request, res: Response) => {
  try {
    const piDir = join(process.cwd(), '.pi-invest');
    const portfolioPath = join(piDir, 'portfolio.json');

    if (!existsSync(portfolioPath)) {
      return res.json({
        success: true,
        data: []
      });
    }

    const portfolio = JSON.parse(readFileSync(portfolioPath, 'utf-8'));

    res.json({
      success: true,
      data: portfolio.holdings || []
    });
  } catch (error) {
    console.error('[Portfolio API] Error fetching holdings:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * 获取交易历史
 * GET /api/portfolio/trades
 */
router.get('/trades', async (req: Request, res: Response) => {
  try {
    const piDir = join(process.cwd(), '.pi-invest');
    const tradesPath = join(piDir, 'trades.json');

    if (!existsSync(tradesPath)) {
      return res.json({
        success: true,
        data: []
      });
    }

    const trades = JSON.parse(readFileSync(tradesPath, 'utf-8'));

    res.json({
      success: true,
      data: Array.isArray(trades) ? trades : []
    });
  } catch (error) {
    console.error('[Portfolio API] Error fetching trades:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * 获取投资组合统计
 * GET /api/portfolio/stats
 */
router.get('/stats', async (req: Request, res: Response) => {
  try {
    const piDir = join(process.cwd(), '.pi-invest');
    const portfolioPath = join(piDir, 'portfolio.json');

    if (!existsSync(portfolioPath)) {
      return res.json({
        success: true,
        data: {
          total_value: 0,
          total_cost: 0,
          total_pnl: 0,
          total_pnl_pct: 0,
          position_count: 0,
          cash: 0
        }
      });
    }

    const portfolio = JSON.parse(readFileSync(portfolioPath, 'utf-8'));

    const stats = {
      total_value: portfolio.total_value || 0,
      total_cost: portfolio.total_cost || 0,
      total_pnl: portfolio.total_pnl || 0,
      total_pnl_pct: portfolio.total_pnl_pct || 0,
      position_count: portfolio.holdings?.length || 0,
      cash: portfolio.cash || 0
    };

    res.json({
      success: true,
      data: stats
    });
  } catch (error) {
    console.error('[Portfolio API] Error fetching stats:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * 健康检查接口
 * GET /api/portfolio/health
 */
router.get('/health', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    service: 'portfolio-api',
    timestamp: new Date().toISOString()
  });
});

export { router as portfolioRouter };
