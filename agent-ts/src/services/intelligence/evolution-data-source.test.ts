/**
 * 回归测试：多账户域上线后（2026-07-21）/api/simulation/trades 强制要求 account_name，
 * 进化/经验数据采集必须显式指定 agent 唯一账本 agent_virtual，
 * 否则后端 400「account_name is required」（2026-08-05 事故）。
 */
import { describe, expect, it, jest, beforeEach } from '@jest/globals';
import { loadTrades, loadPortfolio } from './data-collector.js';
import {
  loadEvolutionTrades,
  loadEvolutionPortfolio,
} from './evolution-service.js';

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockFetch as any;

function okJson(payload: any) {
  return { json: async () => payload } as any;
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe('data-collector 多账户契约', () => {
  it('loadTrades 必须携带 account_name=agent_virtual', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ success: true, data: [] }));
    await loadTrades();
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url).toContain('/api/simulation/trades');
    expect(url).toContain('account_name=agent_virtual');
  });

  it('loadPortfolio 必须读 agent_virtual 账户而非 default', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ success: true, data: { positions: [] } }));
    await loadPortfolio();
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url).toContain('/api/simulation/accounts/agent_virtual');
    expect(url).not.toContain('/accounts/default');
  });
});

describe('evolution-service 多账户契约', () => {
  it('loadEvolutionTrades 必须携带 account_name=agent_virtual', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ success: true, data: [] }));
    await loadEvolutionTrades();
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url).toContain('/api/simulation/trades');
    expect(url).toContain('account_name=agent_virtual');
  });

  it('loadEvolutionPortfolio 必须读 agent_virtual 账户而非 default', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ success: true, data: { positions: [] } }));
    await loadEvolutionPortfolio();
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url).toContain('/api/simulation/accounts/agent_virtual');
  });
});
