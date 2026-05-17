import { Router } from 'express';
import { SignalGenerator } from '../../../services/quant/signal-generator.js';
import { QuantService } from '../../../services/quant/quant-service.js';
import { FactorLibrary } from '../../../services/quant/factor-library.js';
import { readdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';

const router = Router();
const quantService = new QuantService();
const factorLibrary = new FactorLibrary();
const signalGenerator = new SignalGenerator('.pi-invest/quant/signals', factorLibrary);

// POST /api/signals/generate - 生成单个股票信号
router.post('/generate', async (req, res, next) => {
  try {
    const { strategy_id, symbol, name, days = 60 } = req.body;

    if (!strategy_id || !symbol || !name) {
      res.status(400);
      throw new Error('Missing required parameters: strategy_id, symbol, name');
    }

    // 获取策略
    const strategy = await quantService.getStrategy(strategy_id);
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }

    // 计算技术指标
    const tech = await factorLibrary.calculateIndicators(symbol, days);

    // 生成信号
    const signal = await signalGenerator.generateSignal(
      symbol,
      name,
      strategy,
      tech,
      tech.close // 使用最新收盘价
    );

    res.json({ success: true, data: signal });
  } catch (error) {
    next(error);
  }
});

// POST /api/signals/scan - 扫描市场生成多个信号
router.post('/scan', async (req, res, next) => {
  try {
    const { strategy_id, stocks, confidence_threshold = 0.5 } = req.body;

    if (!strategy_id || !stocks || !Array.isArray(stocks)) {
      res.status(400);
      throw new Error('Missing required parameters: strategy_id, stocks (array)');
    }

    // 获取策略
    const strategy = await quantService.getStrategy(strategy_id);
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }

    // 准备股票数据
    const stockData = await Promise.all(
      stocks.map(async (stock: { symbol: string; name: string }) => {
        const tech = await factorLibrary.calculateIndicators(stock.symbol, 60);
        return {
          symbol: stock.symbol,
          name: stock.name,
          price: tech.close,
          tech
        };
      })
    );

    // 扫描市场
    const signals = await signalGenerator.scanMarket(strategy, stockData, confidence_threshold);

    res.json({ success: true, data: signals });
  } catch (error) {
    next(error);
  }
});

// GET /api/signals/history - 获取历史信号
router.get('/history', async (req, res, next) => {
  try {
    const days = req.query.days ? parseInt(req.query.days as string) : 30;
    const signalsDir = '.pi-invest/quant/signals';

    if (!existsSync(signalsDir)) {
      return res.json({ success: true, data: [] });
    }

    // 读取信号文件
    const files = readdirSync(signalsDir)
      .filter(f => f.endsWith('.json'))
      .sort()
      .reverse()
      .slice(0, days);

    const allSignals = [];
    for (const file of files) {
      try {
        const content = readFileSync(join(signalsDir, file), 'utf-8');
        const signals = JSON.parse(content);
        allSignals.push(...signals);
      } catch (error) {
        console.warn(`Failed to read signal file ${file}:`, error);
      }
    }

    res.json({ success: true, data: allSignals });
  } catch (error) {
    next(error);
  }
});

export { router as signalsRouter };
