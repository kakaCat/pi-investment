import { describe, expect, it, vi } from 'vitest';
import { QuantsysV2Client } from '../src/client';

describe('signal_track update 客户端契约', () => {
  it('使用独立 60s 超时并透传受控重算参数与诊断', async () => {
    const client = new QuantsysV2Client({ baseURL: 'http://localhost:5001', timeout: 30000 });
    const put = vi.spyOn((client as any).client, 'put').mockResolvedValue({
      data: {
        success: true,
        data: {
          updated: 1,
          details: { '5d': 0, '10d': 0, '20d': 1 },
          diagnostics: { missing_kline: 0, blocked: [] },
          complete: true,
        },
      },
    });

    const result = await client.updateSignalPerformance({
      signal_date: '2026-10-16', symbol: '002027', refresh: true,
    });

    expect(put).toHaveBeenCalledWith(
      '/api/signals/track/update',
      { signal_date: '2026-10-16', symbol: '002027', refresh: true },
      { timeout: 60000 },
    );
    expect(result.complete).toBe(true);
    expect(result.diagnostics.missing_kline).toBe(0);
  });
});
