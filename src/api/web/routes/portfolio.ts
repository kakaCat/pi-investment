import { Router, Request, Response } from 'express';
import { PositionCliAdapter } from '../../../infrastructure/adapters/cli/position-cli-adapter.js';
import { TradeCliAdapter } from '../../../infrastructure/adapters/cli/trade-cli-adapter.js';
import { AccountCliAdapter } from '../../../infrastructure/adapters/cli/account-cli-adapter.js';

const router = Router();

// 初始化适配器
const positionAdapter = new PositionCliAdapter();
const tradeAdapter = new TradeCliAdapter();
const accountAdapter = new AccountCliAdapter();

/**
 * GET /api/portfolio/summary
 * 获取投资组合概览
 */
router.get('/summary', async (req: Request, res: Response) => {
  try {
    const summary = await positionAdapter.getSummary();

    res.json({
      totalValue: summary.totalMarketValue || 0,
      totalCost: summary.totalCost || 0,
      totalPnl: summary.totalPnl || 0,
      totalPnlPct: summary.totalPnlPct || 0,
      dailyChange: summary.totalPnl || 0, // 前端期望的字段名
      positions: summary.totalPositions || 0
    });
  } catch (error) {
    console.error('获取投资组合概览失败:', error);
    res.status(500).json({
      error: 'Failed to get portfolio summary',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * GET /api/portfolio/positions
 * 获取持仓列表
 */
router.get('/positions', async (req: Request, res: Response) => {
  try {
    const { status, accountId } = req.query;

    const positions = await positionAdapter.list({
      status: status as string,
      accountId: accountId as string
    });

    res.json(positions);
  } catch (error) {
    console.error('获取持仓列表失败:', error);
    res.status(500).json({
      error: 'Failed to get positions',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * GET /api/portfolio/positions/:symbol
 * 获取单个持仓详情
 */
router.get('/positions/:symbol', async (req: Request, res: Response) => {
  try {
    const { symbol } = req.params;
    const { accountId } = req.query;

    const position = await positionAdapter.get(symbol, accountId as string);

    if (!position) {
      return res.status(404).json({ error: 'Position not found' });
    }

    res.json(position);
  } catch (error) {
    console.error('获取持仓详情失败:', error);
    res.status(500).json({
      error: 'Failed to get position',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * GET /api/portfolio/history
 * 获取投资组合历史数据
 */
router.get('/history', async (req: Request, res: Response) => {
  try {
    const { days = 30 } = req.query;

    // TODO: 实现历史数据查询
    // 目前 CLI 没有提供历史数据接口，需要从数据库直接查询
    // 或者从 position_history 表获取

    // 临时返回空数据
    res.json({
      history: [],
      message: 'Portfolio history endpoint not yet implemented. Need to query position_history table.'
    });
  } catch (error) {
    console.error('获取投资组合历史失败:', error);
    res.status(500).json({
      error: 'Failed to get portfolio history',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * GET /api/portfolio/equity-curve
 * 获取资产曲线
 */
router.get('/equity-curve', async (req: Request, res: Response) => {
  try {
    const { startDate, endDate } = req.query;

    // TODO: 实现资产曲线查询
    res.json({
      data: [],
      message: 'Equity curve endpoint not yet implemented'
    });
  } catch (error) {
    console.error('获取资产曲线失败:', error);
    res.status(500).json({
      error: 'Failed to get equity curve',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * GET /api/portfolio/allocation
 * 获取持仓分布
 */
router.get('/allocation', async (req: Request, res: Response) => {
  try {
    const positions = await positionAdapter.list({ status: 'open' });

    // 计算持仓分布
    const allocation = positions.map(pos => ({
      symbol: pos.symbol,
      name: pos.name,
      value: (pos.currentPrice || 0) * pos.quantity,
      percentage: 0 // 需要计算百分比
    }));

    const totalValue = allocation.reduce((sum, item) => sum + item.value, 0);
    allocation.forEach(item => {
      item.percentage = totalValue > 0 ? (item.value / totalValue) * 100 : 0;
    });

    res.json(allocation);
  } catch (error) {
    console.error('获取持仓分布失败:', error);
    res.status(500).json({
      error: 'Failed to get allocation',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

export { router as portfolioRouter };
