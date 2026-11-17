import { describe, expect, it, vi } from 'vitest';
import { SignalTrackTool } from '../../../packages/tools/intelligence/src/tools/SignalTrackTool/SignalTrackTool.js';

describe('signal_track update 工具契约', () => {
  it('缺省不再伪造 30 天窗口，并把缺 K 诊断写进摘要', async () => {
    const updateSignalPerformance = vi.fn().mockResolvedValue({
      updated: 0,
      details: { '5d': 0, '10d': 0, '20d': 0 },
      diagnostics: { not_due: 2, missing_kline: 3, invalid_signal: 0, blocked: [] },
      complete: false,
    });
    const tool: any = new SignalTrackTool({ updateSignalPerformance } as any);

    const result = await tool.execute({ action: 'update' }, {} as any);

    expect(updateSignalPerformance).toHaveBeenCalledWith({
      signal_date: undefined,
      lookback_days: undefined,
      symbol: undefined,
      refresh: undefined,
    });
    expect(result.result).toContain('缺K线 3 项');
    expect(result.result).toContain('未完整');
  });

  it('真实 client 的 camelCase diagnostics 不得被摘要显示成零', async () => {
    const updateSignalPerformance = vi.fn().mockResolvedValue({
      updated: 0,
      details: { '5d': 0, '10d': 0, '20d': 0 },
      diagnostics: { notDue: 136, missingKline: 0, invalidSignal: 1, blocked: [{ signalId: 134 }] },
      complete: false,
    });
    const tool: any = new SignalTrackTool({ updateSignalPerformance } as any);

    const result = await tool.execute({ action: 'update' }, {} as any);

    expect(result.result).toContain('未到期 136 项');
    expect(result.result).toContain('非法信号 1 项');
    expect(result.result).toContain('未完整');
  });

  it('refresh 未限定范围时在入口拒绝', () => {
    const tool: any = new SignalTrackTool({} as any);
    const verdict = tool.validate({ action: 'update', refresh: true });
    expect(verdict.success).toBe(false);
    expect(verdict.issue).toContain('必须同时限定');
  });
});
