import { Router } from 'express';
import { BacktestEngine } from '../../../services/quant/backtest-engine.js';
import { QuantService } from '../../../services/quant/quant-service.js';
import { FactorLibrary } from '../../../services/quant/factor-library.js';

const router = Router();
const quantService = new QuantService();
const factorLibrary = new FactorLibrary();

// POST /api/backtest/run - 运行回测
router.post('/run', async (req, res, next) => {
  try {
    const { strategy_id, symbol, start_date, end_date, initial_capital = 100000 } = req.body;

    if (!strategy_id || !symbol || !start_date || !end_date) {
      res.status(400);
      throw new Error('Missing required parameters: strategy_id, symbol, start_date, end_date');
    }

    // 获取策略
    const strategy = await quantService.getStrategy(strategy_id);
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }

    // 运行回测
    const backtestEngine = new BacktestEngine(factorLibrary);
    const result = await backtestEngine.runBacktest(
      strategy,
      symbol,
      start_date,
      end_date,
      initial_capital
    );

    res.json({ success: true, data: result });
  } catch (error) {
    next(error);
  }
});

export { router as backtestRouter };
