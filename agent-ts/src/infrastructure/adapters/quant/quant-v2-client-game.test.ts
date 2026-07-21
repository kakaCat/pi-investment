/**
 * QuantV2Client 博弈情报路由测试
 *
 * 回归测试: game 工具必须通过 V2_ROUTES 命令映射调用后端，
 * 直接传 URL 路径会触发 "没有 v2 端点映射" 错误。
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';

// Mock global fetch
const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockFetch;

// Import after mocking
import { runQuantV2 } from './quant-v2-client.js';

describe('QuantV2Client Game Intelligence Routes', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('market.manipulation_detect should map to /api/game/market/manipulation-detect', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          active_manipulations: [],
          post_manipulation_opportunities: [],
          timestamp: '2026-07-18T22:36:27.627476',
        },
      }),
    } as Response);

    const result = await runQuantV2('market.manipulation_detect', {});

    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:5001/api/game/market/manipulation-detect',
      expect.objectContaining({ method: 'GET' })
    );
    expect(result.ok).toBe(true);
  });

  it('pool.battlefield_assessment should fill {pool_id} path placeholder from params', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { pool_id: 5, battlefield_score: 78.5 },
      }),
    } as Response);

    const result = await runQuantV2('pool.battlefield_assessment', { pool_id: 5 });

    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:5001/api/game/pools/5/battlefield-assessment',
      expect.objectContaining({ method: 'GET' })
    );
    expect(result.ok).toBe(true);
  });
});
