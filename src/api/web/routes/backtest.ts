import { Router } from 'express';
import { BacktestEngine } from '../../../services/quant/backtest-engine.js';
import { QuantService } from '../../../services/quant/quant-service.js';
import { FactorLibrary } from '../../../services/quant/factor-library.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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

// GET /api/backtest/results - 获取回测结果汇总
router.get('/results', async (req, res, next) => {
  try {
    // 检查多个可能的回测结果目录
    const possibleDirs = [
      path.join(__dirname, '../../../../.pi-invest/quant/backtest'),
      path.join(__dirname, '../../../../quant/quantsys/backtest/results'),
      path.join(__dirname, '../../../../quant/backtest')
    ];

    let backtestDir: string | null = null;
    for (const dir of possibleDirs) {
      if (fs.existsSync(dir)) {
        backtestDir = dir;
        break;
      }
    }

    if (!backtestDir) {
      res.json({ summary: [] });
      return;
    }

    const files = fs.readdirSync(backtestDir)
      .filter(f => f.endsWith('.json'))
      .sort()
      .reverse();

    const summary = files.slice(0, 100).map(filename => {
      try {
        const filePath = path.join(backtestDir!, filename);
        const content = fs.readFileSync(filePath, 'utf-8');
        const data = JSON.parse(content);

        return {
          symbol: data.symbol || '',
          date: data.date || data.backtest_date || '',
          best_strategy: data.best_strategy || data.strategy || '',
          best_return: data.total_return || data.best_return || 0,
          sharpe_ratio: data.sharpe_ratio || 0,
          max_drawdown: data.max_drawdown || 0,
          win_rate: data.win_rate || 0
        };
      } catch (error) {
        console.warn(`Failed to parse backtest result ${filename}:`, error);
        return null;
      }
    }).filter(record => record !== null);

    res.json({ summary });
  } catch (error) {
    next(error);
  }
});

export { router as backtestRouter };
