import { describe, expect, it, vi } from 'vitest';
import { KlineDailySyncTool } from '../../../packages/tools/data-manager/src/tools/KlineDailySyncTool/KlineDailySyncTool.js';

describe('kline_daily_sync 显式修复契约', () => {
  it('force 必须限定标的，source 不得单独使用', () => {
    const tool: any = new KlineDailySyncTool({} as any);
    expect(tool.validate({ force: true }).success).toBe(false);
    expect(tool.validate({ date: '2026-11-13', source: 'akshare' }).success).toBe(false);
    expect(tool.validate({
      date: '2026-11-13', symbols: ['002027'], force: true, source: 'akshare',
    }).success).toBe(true);
  });

  it('透传双源修复证据而不经正常回填字段吞掉', async () => {
    const syncDailyKlines = vi.fn().mockResolvedValue({
      success: true, sync_date: '2026-11-13', success_count: 1,
      failed_count: 0, total_stocks: 1, total_rows: 1, elapsed_time: 1.2,
      message: '双源核验修复完成', failed_symbols: [],
      details: [{ symbol: '002027', cross_validated: true, before: [{ close: 5.29 }], after: [{ close: 5.49 }] }],
    });
    const tool: any = new KlineDailySyncTool({ syncDailyKlines } as any);
    const result = await tool.execute({
      date: '2026-11-13', symbols: ['002027'], force: true, source: 'akshare',
    }, {} as any);

    expect(syncDailyKlines).toHaveBeenCalledWith({
      date: '2026-11-13', symbols: ['002027'], force: true, source: 'akshare',
    });
    expect(result.repair_details[0].cross_validated).toBe(true);
    expect(result.repair_details[0].after[0].close).toBe(5.49);
  });
});
