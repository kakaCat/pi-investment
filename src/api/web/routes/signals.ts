import { Router } from 'express';
import { requireOpsAuth } from '../middleware/ops-auth.js';
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

const router = Router();

// LEGACY: helper functions for TS-based signal generation - kept for rollback
// async function calculateIndicators(symbol: string, days: number): Promise<IndicatorsWithClose> { ... }
// async function getQuantService(): Promise<QuantService> { ... }
// async function getFactorLibrary(): Promise<FactorLibrary> { ... }
// async function getSignalGenerator(): Promise<SignalGenerator> { ... }

// NEW: proxy to Python backend
router.get('/', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/signals', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// LEGACY: file-based signal reading with filtering - kept for rollback
// router.get('/', async (req, res, next) => {
//   try {
//     const date = req.query.date as string | undefined;
//     const signalType = req.query.signal_type as string | undefined;
//     const minConfidence = req.query.min_confidence ? parseFloat(req.query.min_confidence as string) : undefined;
//     const signalsPath = getSignalsFilePath();
//     if (!fs.existsSync(signalsPath)) {
//       return res.json({ signals: [], count: 0, date: '' });
//     }
//     const rawData = fs.readFileSync(signalsPath, 'utf-8');
//     const data = JSON.parse(rawData);
//     let signals = data.signals || [];
//     if (!Array.isArray(signals)) {
//       signals = [];
//     }
//     if (date) {
//       signals = signals.filter((s: any) => s.date === date);
//     }
//     if (signalType) {
//       signals = signals.filter((s: any) => s.signal === signalType);
//     }
//     if (minConfidence !== undefined) {
//       signals = signals.filter((s: any) => (s.confidence || 0) >= minConfidence);
//     }
//     res.json({
//       signals,
//       count: signals.length,
//       date: data.date || ''
//     });
//   } catch (error) {
//     next(error);
//   }
// });

// LEGACY: TS-based single stock signal generation - kept for rollback (not migrated)
// router.post('/generate', requireOpsAuth(), async (req, res, next) => {
//   try {
//     const { strategy_id, symbol, name, days = 60 } = req.body;
//     if (!strategy_id || !symbol || !name) {
//       res.status(400);
//       throw new Error('Missing required parameters: strategy_id, symbol, name');
//     }
//     const strategy = await (await getQuantService()).getStrategy(strategy_id);
//     if (!strategy) {
//       res.status(404);
//       throw new Error('Strategy not found');
//     }
//     const tech = await calculateIndicators(symbol, days);
//     const signal = await (await getSignalGenerator()).generateSignal(
//       symbol,
//       name,
//       strategy,
//       tech,
//       tech.close
//     );
//     res.json({ success: true, data: signal });
//   } catch (error) {
//     next(error);
//   }
// });

// NEW: proxy to Python backend
router.post('/scan', requireOpsAuth(), async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.post('/api/signals/scan', req.body);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// LEGACY: TS-based market scanning with signal generation - kept for rollback
// router.post('/scan', requireOpsAuth(), async (req, res, next) => {
//   try {
//     const { strategy_id, stocks, confidence_threshold = 0.5 } = req.body;
//     if (!strategy_id || !stocks || !Array.isArray(stocks)) {
//       res.status(400);
//       throw new Error('Missing required parameters: strategy_id, stocks (array)');
//     }
//     const strategy = await (await getQuantService()).getStrategy(strategy_id);
//     if (!strategy) {
//       res.status(404);
//       throw new Error('Strategy not found');
//     }
//     const stockData = await Promise.all(
//       stocks.map(async (stock: { symbol: string; name: string }) => {
//         const tech = await calculateIndicators(stock.symbol, 60);
//         return {
//           symbol: stock.symbol,
//           name: stock.name,
//           price: tech.close,
//           tech
//         };
//       })
//     );
//     const signals = await (await getSignalGenerator()).scanMarket(strategy, stockData, confidence_threshold);
//     res.json({ success: true, data: signals });
//   } catch (error) {
//     next(error);
//   }
// });

// NEW: proxy to Python backend
router.get('/history', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/signals', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// LEGACY: quant-python-client based history fetching - kept for rollback
// router.get('/history', async (req, res, next) => {
//   try {
//     const query = new URLSearchParams(req.query as Record<string, string>).toString();
//     const data = await requestQuantPythonApi<unknown>(`/api/signals${query ? `?${query}` : ''}`, {
//       method: 'GET'
//     });
//     res.json({ success: true, data });
//   } catch (error) {
//     if (error instanceof QuantPythonApiError) {
//       sendQuantApiError(res, error);
//       return;
//     }
//     next(error);
//   }
// });

export { router as signalsRouter };
