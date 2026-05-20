import { Router, type Response } from 'express';
import type { SignalGenerator } from '../../../services/quant/signal-generator.js';
import type { QuantService } from '../../../services/quant/quant-service.js';
import type { FactorLibrary, TechnicalIndicators } from '../../../services/quant/factor-library.js';
import { QuantPythonApiError, requestQuantPythonApi } from './quant-python-client.js';
import { requireOpsAuth } from '../middleware/ops-auth.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const router = Router();
let quantService: QuantService | undefined;
let factorLibrary: FactorLibrary | undefined;
let signalGenerator: SignalGenerator | undefined;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

type IndicatorsWithClose = TechnicalIndicators & { close: number };

function sendQuantApiError(res: Response, error: QuantPythonApiError): void {
  if (typeof error.details === 'object' && error.details !== null) {
    res.status(error.status).json(error.details);
    return;
  }
  res.status(error.status).json({ error: error.message });
}

function getSignalsFilePath(): string {
  const projectRoot = path.resolve(__dirname, '../../../../');
  const paths = [
    path.join(projectRoot, 'quant', '.pi-invest', 'signals.json'),
    path.join(projectRoot, '.pi-invest', 'signals.json'),
  ];
  for (const p of paths) {
    if (fs.existsSync(p)) {
      return p;
    }
  }
  return paths[0];
}

async function calculateIndicators(symbol: string, days: number): Promise<IndicatorsWithClose> {
  const library = await getFactorLibrary();
  const [rsi, ma5, ma10, ma20, ma60, macd, bb, fundamentals, close] = await Promise.all([
    library.calculateRSIForSymbol(symbol, 14),
    library.calculateMAForSymbol(symbol, 5),
    library.calculateMAForSymbol(symbol, 10),
    library.calculateMAForSymbol(symbol, 20),
    library.calculateMAForSymbol(symbol, Math.max(60, days)),
    library.calculateMACDForSymbol(symbol),
    library.calculateBollingerBands(symbol, 20, 2),
    library.getFundamentals(symbol),
    library.getLatestClosePrice(symbol)
  ]);

  return {
    rsi,
    ma5,
    ma10,
    ma20,
    ma60,
    macd_dif: macd.dif,
    macd_dea: macd.dea,
    macd_histogram: macd.macd,
    bollinger_upper: bb.upper,
    bollinger_mid: bb.middle,
    bollinger_lower: bb.lower,
    volume_ratio: 1,
    atr: 0,
    pe: fundamentals.pe,
    pb: fundamentals.pb,
    roe: fundamentals.roe,
    gross_margin: fundamentals.gross_margin,
    debt_ratio: fundamentals.debt_ratio,
    close
  };
}

async function getQuantService(): Promise<QuantService> {
  if (!quantService) {
    const { QuantService } = await import('../../../services/quant/quant-service.js');
    quantService = new QuantService();
  }
  return quantService;
}

async function getFactorLibrary(): Promise<FactorLibrary> {
  if (!factorLibrary) {
    const [{ FactorLibrary }, { StockDBService }] = await Promise.all([
      import('../../../services/quant/factor-library.js'),
      import('../../../services/data/stock-db-service.js'),
    ]);
    factorLibrary = new FactorLibrary(StockDBService.getInstance('.pi-invest'));
  }
  return factorLibrary;
}

async function getSignalGenerator(): Promise<SignalGenerator> {
  if (!signalGenerator) {
    const [{ SignalGenerator }, library] = await Promise.all([
      import('../../../services/quant/signal-generator.js'),
      getFactorLibrary(),
    ]);
    signalGenerator = new SignalGenerator('.pi-invest/quant/signals', library, true);
  }
  return signalGenerator;
}

// GET /api/signals - quant-web compatibility endpoint
router.get('/', async (req, res, next) => {
  try {
    const date = req.query.date as string | undefined;
    const signalType = req.query.signal_type as string | undefined;
    const minConfidence = req.query.min_confidence ? parseFloat(req.query.min_confidence as string) : undefined;

    const signalsPath = getSignalsFilePath();
    
    if (!fs.existsSync(signalsPath)) {
      return res.json({ signals: [], count: 0, date: '' });
    }

    const rawData = fs.readFileSync(signalsPath, 'utf-8');
    const data = JSON.parse(rawData);
    
    let signals = data.signals || [];
    if (!Array.isArray(signals)) {
      signals = [];
    }

    if (date) {
      signals = signals.filter((s: any) => s.date === date);
    }
    if (signalType) {
      signals = signals.filter((s: any) => s.signal === signalType);
    }
    if (minConfidence !== undefined) {
      signals = signals.filter((s: any) => (s.confidence || 0) >= minConfidence);
    }

    res.json({
      signals,
      count: signals.length,
      date: data.date || ''
    });
  } catch (error) {
    next(error);
  }
});

// POST /api/signals/generate - 生成单个股票信号
router.post('/generate', requireOpsAuth(), async (req, res, next) => {
  try {
    const { strategy_id, symbol, name, days = 60 } = req.body;

    if (!strategy_id || !symbol || !name) {
      res.status(400);
      throw new Error('Missing required parameters: strategy_id, symbol, name');
    }

    // 获取策略
    const strategy = await (await getQuantService()).getStrategy(strategy_id);
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }

    // 计算技术指标
    const tech = await calculateIndicators(symbol, days);

    // 生成信号
    const signal = await (await getSignalGenerator()).generateSignal(
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
router.post('/scan', requireOpsAuth(), async (req, res, next) => {
  try {
    const { strategy_id, stocks, confidence_threshold = 0.5 } = req.body;

    if (!strategy_id || !stocks || !Array.isArray(stocks)) {
      res.status(400);
      throw new Error('Missing required parameters: strategy_id, stocks (array)');
    }

    // 获取策略
    const strategy = await (await getQuantService()).getStrategy(strategy_id);
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }

    // 准备股票数据
    const stockData = await Promise.all(
      stocks.map(async (stock: { symbol: string; name: string }) => {
        const tech = await calculateIndicators(stock.symbol, 60);
        return {
          symbol: stock.symbol,
          name: stock.name,
          price: tech.close,
          tech
        };
      })
    );

    // 扫描市场
    const signals = await (await getSignalGenerator()).scanMarket(strategy, stockData, confidence_threshold);

    res.json({ success: true, data: signals });
  } catch (error) {
    next(error);
  }
});

// GET /api/signals/history - 获取历史信号
router.get('/history', async (req, res, next) => {
  try {
    const query = new URLSearchParams(req.query as Record<string, string>).toString();
    const data = await requestQuantPythonApi<unknown>(`/api/signals${query ? `?${query}` : ''}`, {
      method: 'GET'
    });
    res.json({ success: true, data });
  } catch (error) {
    if (error instanceof QuantPythonApiError) {
      sendQuantApiError(res, error);
      return;
    }
    next(error);
  }
});

export { router as signalsRouter };
