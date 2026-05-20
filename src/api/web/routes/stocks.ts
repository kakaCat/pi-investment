import { Router, type Response } from 'express';
import { QuantPythonApiError, requestQuantPythonApi } from './quant-python-client.js';

export const stocksRouter = Router();

function sendQuantApiError(res: Response, error: QuantPythonApiError): void {
  if (typeof error.details === 'object' && error.details !== null) {
    res.status(error.status).json(error.details);
    return;
  }
  res.status(error.status).json({ error: error.message });
}

// GET /api/stocks/data-status - 获取股票数据完整性统计
// Note: This must come before /:symbol to avoid route collision
stocksRouter.get('/data-status', async (req, res, next) => {
  try {
    const query = new URLSearchParams(req.query as Record<string, string>).toString();
    const data = await requestQuantPythonApi<unknown>(`/api/stocks/data-status${query ? `?${query}` : ''}`, {
      method: 'GET'
    });
    res.json(data);
  } catch (error) {
    if (error instanceof QuantPythonApiError) {
      sendQuantApiError(res, error);
      return;
    }
    next(error);
  }
});

// POST /api/stocks/compare - quant-web compatibility endpoint
stocksRouter.post('/compare', async (req, res) => {
  const symbols = Array.isArray(req.body?.symbols) ? req.body.symbols : [];

  if (symbols.length === 0) {
    res.status(400).json({ error: '请提供股票代码' });
    return;
  }

  if (symbols.length > 5) {
    res.status(400).json({ error: '最多对比5只股票' });
    return;
  }

  try {
    const data = await requestQuantPythonApi<unknown>('/api/stocks/compare', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ...req.body, symbols })
    });
    res.json(data);
  } catch (error) {
    if (error instanceof QuantPythonApiError) {
      sendQuantApiError(res, error);
      return;
    }
    throw error;
  }
});

stocksRouter.post('/resolve', async (req, res, next) => {
  try {
    const symbols = normalizeRequestSymbols(req.body?.symbols);
    if (symbols.length === 0) {
      res.status(400);
      throw new Error('请提供股票代码');
    }

    const data = await requestQuantPythonApi<unknown>('/api/stocks/resolve', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ...req.body, symbols })
    });
    res.json(data);
  } catch (error) {
    if (error instanceof QuantPythonApiError) {
      sendQuantApiError(res, error);
      return;
    }
    next(error);
  }
});

// 市场概览
stocksRouter.get('/market/overview', async (_req, res, next) => {
  try {
    const { get_market_overview } = await import('../../../infrastructure/akshare-ts/index.js');
    const overviewStr = await get_market_overview();
    const overview = JSON.parse(overviewStr);
    res.json({ success: true, data: overview });
  } catch (e) {
    next(e);
  }
});

function normalizeRequestSymbols(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item));
  }
  if (typeof value === 'string') {
    return value.split(/[\s,，]+/).filter(Boolean);
  }
  return [];
}

// 获取股票因子分析
stocksRouter.get('/:symbol/factors', async (req, res, next) => {
  try {
    const { symbol } = req.params;
    const query = new URLSearchParams(req.query as Record<string, string>).toString();
    const data = await requestQuantPythonApi<unknown>(
      `/api/stock/${encodeURIComponent(symbol)}/factors${query ? `?${query}` : ''}`,
      { method: 'GET' }
    );
    res.json(data);
  } catch (e) {
    if (e instanceof QuantPythonApiError) {
      sendQuantApiError(res, e);
      return;
    }
    next(e);
  }
});

// 获取单只股票信息 + 实时行情
// Note: This must come last as it's a catch-all parameterized route
stocksRouter.get('/:symbol', async (req, res, next) => {
  try {
    const { symbol } = req.params;
    const { get_stock_info, get_stock_realtime_price } = await import('../../../infrastructure/akshare-ts/index.js');
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
