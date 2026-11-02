import { describe, expect, it, vi } from 'vitest';
import { QuantsysV2Client } from '../src/client';

describe('投资评价客户端契约', () => {
  it('显式透传账户、日期与资金成本，并解开 data 包装', async () => {
    const client = new QuantsysV2Client({ baseURL: 'http://localhost:5001', timeout: 5000 });
    const get = vi.spyOn((client as any).client, 'get').mockResolvedValue({
      data: { success: true, data: { schemaVersion: 'investment_evaluation_v1', readOnly: true } },
    });
    const result = await client.getInvestmentEvaluationReport({
      account_name: 'test_account', start_date: '2026-09-01', end_date: '2026-11-02', annual_cost_rate: 0.02,
    });
    expect(get).toHaveBeenCalledWith('/api/evaluation/report', { params: {
      account_name: 'test_account', start_date: '2026-09-01', end_date: '2026-11-02', annual_cost_rate: 0.02,
    } });
    expect(result.readOnly).toBe(true);
  });

  it('success:false 不得静默当报告成功', async () => {
    const client = new QuantsysV2Client({ baseURL: 'http://localhost:5001', timeout: 5000 });
    vi.spyOn((client as any).client, 'get').mockResolvedValue({
      data: { success: false, error: 'evaluation_unavailable' },
    });
    await expect(client.getInvestmentEvaluationReport({ account_name: 'test_account' }))
      .rejects.toThrow('evaluation_unavailable');
  });
});
