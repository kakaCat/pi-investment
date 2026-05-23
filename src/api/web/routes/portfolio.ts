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
    // 获取持仓汇总
    const summary = await positionAdapter.getSummary();

    // 获取账户现金
    const account = await accountAdapter.get('Default Account');
    const cash = account?.currentCapital || 0;

    // 计算总资产 = 持仓市值 + 现金
    // 注意：如果 current_price 为 null，totalMarketValue 会是 0
    const totalValue = (summary.totalMarketValue || summary.totalCost || 0) + cash;

    res.json({
      totalValue: totalValue,
      totalCost: summary.totalCost || 0,
      totalPnl: summary.totalPnl || 0,
      totalPnlPct: summary.totalPnlPct || 0,
      dailyChange: summary.totalPnl || 0, // 前端期望的字段名
      positions: summary.totalPositions || 0,
      cash: cash
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
    const daysNum = parseInt(days as string, 10);

    // 从数据库查询历史数据
    const { Client } = await import('pg');
    const connectionString = process.env.QUANT_DATABASE_URL
      || process.env.DATABASE_URL
      || process.env.POSTGRES_DSN;

    const client = new Client(connectionString
      ? { connectionString }
      : {
          database: process.env.PGDATABASE || 'quant_investment',
          host: process.env.PGHOST || 'localhost',
          port: process.env.PGPORT ? Number(process.env.PGPORT) : 5432,
          user: process.env.PGUSER || 'mac',
          password: process.env.PGPASSWORD,
        });

    await client.connect();

    try {
      // 获取当前账户现金
      const accountResult = await client.query(`
        SELECT current_capital FROM quant_agent.accounts LIMIT 1
      `);
      const currentCash = accountResult.rows[0]?.current_capital || 0;

      // 获取当前持仓成本
      const positionsResult = await client.query(`
        SELECT SUM(quantity * cost_basis) as total_cost
        FROM quant_agent.positions
        WHERE status = 'open'
      `);
      const totalCost = parseFloat(positionsResult.rows[0]?.total_cost) || 0;

      // 计算当前总资产（成本价）= 持仓成本 + 现金
      const currentTotalAssets = totalCost + currentCash;

      // 生成历史数据（简化版：假设总资产保持相对稳定）
      // TODO: 实际应该从 position_history 重建每日快照
      const history = [];
      const today = new Date();

      for (let i = daysNum - 1; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(date.getDate() - i);

        // 简化计算：基于当前总资产加上随机波动
        // 实际应该从历史交易记录重建
        const randomFactor = 0.98 + Math.random() * 0.04; // ±2% 波动
        const assets = currentTotalAssets * randomFactor;

        history.push({
          date: date.toISOString().split('T')[0],
          totalAssets: Math.round(assets)
        });
      }

      res.json({
        history,
        note: 'Simplified calculation. TODO: Rebuild from position_history table.'
      });
    } finally {
      await client.end();
    }
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
