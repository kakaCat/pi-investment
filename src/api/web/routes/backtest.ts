import { Router } from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { requireOpsAuth } from '../middleware/ops-auth.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const router = Router();
type QuantServiceInstance = import('../../../services/quant/quant-service.js').QuantService;
type StockDBServiceInstance = import('../../../services/data/stock-db-service.js').StockDBService;

let quantService: QuantServiceInstance | undefined;
let stockDBService: StockDBServiceInstance | undefined;

async function getQuantService(): Promise<QuantServiceInstance> {
  if (!quantService) {
    const { QuantService } = await import('../../../services/quant/quant-service.js');
    quantService = new QuantService();
  }
  return quantService;
}

async function getStockDBService(): Promise<StockDBServiceInstance> {
  if (!stockDBService) {
    const { StockDBService } = await import('../../../services/data/stock-db-service.js');
    stockDBService = StockDBService.getInstance('.pi-invest');
  }
  return stockDBService;
}

// POST /api/backtest/run - 运行回测
router.post('/run', requireOpsAuth(), async (req, res, next) => {
  try {
    const { strategy_id, symbol, start_date, end_date, initial_capital = 100000 } = req.body;

    if (!strategy_id || !symbol || !start_date || !end_date) {
      res.status(400);
      throw new Error('Missing required parameters: strategy_id, symbol, start_date, end_date');
    }

    // 获取策略
    const strategy = await (await getQuantService()).getStrategy(strategy_id);
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }

    // 运行回测
    const symbols = Array.isArray(symbol) ? symbol : [symbol];
    const { BacktestEngine } = await import('../../../services/quant/backtest-engine.js');
    const backtestEngine = new BacktestEngine(await getStockDBService());
    const result = await backtestEngine.runBacktest(
      strategy,
      start_date,
      end_date,
      symbols,
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
    const symbol = typeof req.query.symbol === 'string' ? req.query.symbol : undefined;
    const date = typeof req.query.date === 'string' ? req.query.date : undefined;
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
      res.json({ count: 0, summary: [] });
      return;
    }

    const files = fs.readdirSync(backtestDir)
      .filter(f => f.endsWith('.json'))
      .sort()
      .reverse();

    const records = files.map(filename => {
      try {
        const filePath = path.join(backtestDir!, filename);
        const content = fs.readFileSync(filePath, 'utf-8');
        const data = JSON.parse(content);

        return {
          filename,
          raw: data,
          symbol: data.symbol || '',
          date: data.date || data.backtest_date || data.report_date || '',
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

    if (symbol && date) {
      const detail = records.find(record => record.symbol === symbol && record.date === date);
      if (!detail) {
        res.json({ count: 0, reports: [], summary: [] });
        return;
      }
      res.json({ count: 1, ...detail.raw, filename: detail.filename });
      return;
    }

    if (symbol) {
      const reports = records
        .filter(record => record.symbol === symbol)
        .map(record => ({ filename: record.filename, ...record.raw }));
      res.json({ count: reports.length, reports });
      return;
    }

    const summary = records.slice(0, 100).map(({ raw, ...record }) => record);

    res.json({ count: summary.length, summary });
  } catch (error) {
    next(error);
  }
});

export { router as backtestRouter };
