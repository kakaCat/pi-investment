/**
 * QuantV2 Client Tests - Factor Analysis & Dividend Data
 *
 * 2026-08-05：mock 全局 fetch（原直连 127.0.0.1:5001，全量跑白等 60s+）。
 * 断言目标 = 客户端的请求构造与响应解析，罐头响应按 v2 信封 {success, data}。
 */
import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { analyzeFactors, getDividends, runQuantV2 } from './quant-v2-client.js';
import type { FactorAnalyzeParams } from './types.js';

const realFetch = globalThis.fetch;

function mockV2Fetch() {
  globalThis.fetch = jest.fn(async (input: any, init?: any) => {
    const url = String(input);
    let body: any;
    if (url.includes('/api/portfolio/factor-analyze')) {
      // 按请求体的因子列表回显（测客户端解析，不测后端计算）
      let requested: string[] = ['rsi'];
      try {
        const payload = JSON.parse(init?.body ?? '{}');
        if (Array.isArray(payload.factors) && payload.factors.length > 0) {
          requested = payload.factors;
        }
      } catch { /* 保持默认 */ }
      body = {
        success: true,
        data: {
          success: true,
          factors: requested.map((name: string) => ({
            name,
            coverage: 0.95,
            data_points: 500,
            ic_daily: 0.03,
            ic_weekly: 0.05,
            ic_monthly: 0.08,
            stability: 0.7,
            decay_curve: [0.03, 0.05],
          })),
          method: 'fallback',
        },
      };
    } else if (url.includes('/api/stock/') && url.includes('/dividends')) {
      body = {
        success: true,
        symbol: '600519.SH',
        dividends: [{ year: 2025, dps: 30.0, yield: 1.7 }],
      };
    } else if (url.includes('/api/dividends/screen')) {
      body = {
        success: true,
        stocks: [{ symbol: '600519.SH', yield: 3.5 }],
      };
    } else if (url.includes('/api/dividends/calendar')) {
      body = {
        success: true,
        events: [{ symbol: '600519.SH', date: '2026-06-15' }],
        event_type: '除权除息日',
      };
    } else {
      body = { success: true, data: {} };
    }
    return {
      ok: true,
      status: 200,
      json: async () => body,
      text: async () => JSON.stringify(body),
    } as Response;
  }) as any;
}

beforeEach(() => {
  mockV2Fetch();
});

afterEach(() => {
  globalThis.fetch = realFetch;
});

describe('QuantV2Client - Factor Analysis', () => {
  describe('analyzeFactors', () => {
    it('should return properly formatted factor analysis with snake_case fields', async () => {
      const params: FactorAnalyzeParams = {
        factors: ['rsi', 'macd'],
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      };

      const result = await analyzeFactors(params);

      // 验证响应结构
      expect(result).toHaveProperty('success');
      expect(result).toHaveProperty('factors');
      expect(result.success).toBe(true);
      expect(Array.isArray(result.factors)).toBe(true);
      expect(result.factors.length).toBeGreaterThan(0);

      // 验证因子字段使用 snake_case（不是 camelCase）
      const factor = result.factors[0];
      expect(factor).toHaveProperty('name');
      expect(factor).toHaveProperty('ic_daily');
      expect(factor).toHaveProperty('ic_weekly');
      expect(factor).toHaveProperty('ic_monthly');
      expect(factor).toHaveProperty('coverage');
      expect(factor).toHaveProperty('stability');
      expect(factor).toHaveProperty('decay_curve');

      // 验证字段类型
      expect(typeof factor.name).toBe('string');
      expect(typeof factor.ic_daily).toBe('number');
      expect(typeof factor.ic_weekly).toBe('number');
      expect(typeof factor.ic_monthly).toBe('number');
      expect(typeof factor.coverage).toBe('number');
      expect(typeof factor.stability).toBe('number');
      expect(Array.isArray(factor.decay_curve)).toBe(true);

      // 验证不存在 camelCase 字段（防止回归）
      expect(factor).not.toHaveProperty('icDaily');
      expect(factor).not.toHaveProperty('icWeekly');
      expect(factor).not.toHaveProperty('icMonthly');
      expect(factor).not.toHaveProperty('decayCurve');
    });

    it('should handle multiple factors', async () => {
      const params: FactorAnalyzeParams = {
        factors: ['rsi', 'macd', 'roe'],
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      };

      const result = await analyzeFactors(params);

      expect(result.success).toBe(true);
      expect(result.factors.length).toBe(3);

      // 验证所有因子都有正确的字段
      result.factors.forEach(factor => {
        expect(factor).toHaveProperty('ic_daily');
        expect(factor).toHaveProperty('ic_weekly');
        expect(factor).toHaveProperty('ic_monthly');
        expect(factor).toHaveProperty('decay_curve');
      });
    });

    it('should throw error for empty factors list', async () => {
      const params: FactorAnalyzeParams = {
        factors: [],
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      };

      await expect(analyzeFactors(params)).rejects.toThrow('因子列表不能为空');
    });

    it('should throw error for missing dates', async () => {
      const params = {
        factors: ['rsi'],
        start_date: '',
        end_date: '',
      } as FactorAnalyzeParams;

      await expect(analyzeFactors(params)).rejects.toThrow('开始日期和结束日期不能为空');
    });
  });

  describe('getDividends', () => {
    it('should fetch single stock dividends', async () => {
      const result = await getDividends({
        mode: 'single',
        symbol: '600519.SH',
        years: 5
      });

      // Backend may return success=false with error if data unavailable
      expect(result).toHaveProperty('success');
      if (result.success) {
        expect(result.symbol).toBe('600519.SH');
        expect(result.dividends).toBeDefined();
        expect(Array.isArray(result.dividends)).toBe(true);
      } else {
        expect(result.error).toBeDefined();
      }
    });

    it('should throw error when symbol missing in single mode', async () => {
      await expect(
        getDividends({ mode: 'single' })
      ).rejects.toThrow('single 模式必须提供 symbol 参数');
    });

    it('should fetch dividend screening results', async () => {
      const result = await getDividends({
        mode: 'screen',
        min_yield: 3.0,
        limit: 10
      });

      expect(result.success).toBe(true);
      expect(result.stocks).toBeDefined();
      expect(Array.isArray(result.stocks)).toBe(true);
    });

    it('should fetch dividend calendar', async () => {
      const result = await getDividends({
        mode: 'calendar',
        start_date: '2026-06-01',
        end_date: '2026-06-30',
        event: 'ex_dividend'
      });

      expect(result.success).toBe(true);
      expect(result.events).toBeDefined();
      expect(result.event_type).toBe('除权除息日');
    });

    it('should throw error when dates missing in calendar mode', async () => {
      await expect(
        getDividends({ mode: 'calendar' })
      ).rejects.toThrow('calendar 模式必须提供 start_date 和 end_date 参数');
    });
  });
});

/**
 * 瞬时故障有界重试（2026-08-05 新增）
 *
 * 契约：默认最多 2 次重试（共 3 次尝试），指数退避；
 * 仅瞬时故障重试（网络错误 / HTTP 502/503/504 / 超时），
 * 4xx 与业务错误不重试；QUANT_CLIENT_RETRY=0 可关闭。
 * 测试将退避基数压到 1ms（QUANT_CLIENT_RETRY_DELAY_MS）避免真实等待。
 */
describe('QuantV2Client - transient retry', () => {
  const RETRY_ENV = 'QUANT_CLIENT_RETRY';
  const DELAY_ENV = 'QUANT_CLIENT_RETRY_DELAY_MS';
  let savedRetry: string | undefined;
  let savedDelay: string | undefined;

  function httpResponse(status: number, body: any = {}): Response {
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText: `HTTP_${status}`,
      json: async () => body,
      text: async () => JSON.stringify(body),
    } as Response;
  }

  beforeEach(() => {
    savedRetry = process.env[RETRY_ENV];
    savedDelay = process.env[DELAY_ENV];
    delete process.env[RETRY_ENV];
    process.env[DELAY_ENV] = '1';
  });

  afterEach(() => {
    if (savedRetry === undefined) delete process.env[RETRY_ENV];
    else process.env[RETRY_ENV] = savedRetry;
    if (savedDelay === undefined) delete process.env[DELAY_ENV];
    else process.env[DELAY_ENV] = savedDelay;
  });

  it('瞬时 503 后成功 → 自动重试并返回结果', async () => {
    let calls = 0;
    globalThis.fetch = jest.fn(async () => {
      calls++;
      if (calls === 1) return httpResponse(503, { error: 'bad gateway' });
      return httpResponse(200, { success: true, data: { stocks: [] } });
    }) as any;

    const result = await runQuantV2('stock.list');

    expect(result.ok).toBe(true);
    expect(calls).toBe(2);
  });

  it('持续 503 → 重试 2 次耗尽后报错（共 3 次尝试）', async () => {
    let calls = 0;
    globalThis.fetch = jest.fn(async () => {
      calls++;
      return httpResponse(503, { error: 'unavailable' });
    }) as any;

    await expect(runQuantV2('stock.list')).rejects.toThrow('HTTP 503');
    expect(calls).toBe(3);
  });

  it('网络错误后成功 → 自动重试并返回结果', async () => {
    let calls = 0;
    globalThis.fetch = jest.fn(async () => {
      calls++;
      if (calls === 1) throw new TypeError('fetch failed');
      return httpResponse(200, { success: true, data: { stocks: [] } });
    }) as any;

    const result = await runQuantV2('stock.list');

    expect(result.ok).toBe(true);
    expect(calls).toBe(2);
  });

  it('4xx → 不重试，立即报错', async () => {
    let calls = 0;
    globalThis.fetch = jest.fn(async () => {
      calls++;
      return httpResponse(400, { error: 'bad request' });
    }) as any;

    await expect(runQuantV2('stock.list')).rejects.toThrow('HTTP 400');
    expect(calls).toBe(1);
  });

  it('QUANT_CLIENT_RETRY=0 → 503 不重试直接报错', async () => {
    process.env[RETRY_ENV] = '0';
    let calls = 0;
    globalThis.fetch = jest.fn(async () => {
      calls++;
      return httpResponse(503, { error: 'unavailable' });
    }) as any;

    await expect(runQuantV2('stock.list')).rejects.toThrow('HTTP 503');
    expect(calls).toBe(1);
  });
});
