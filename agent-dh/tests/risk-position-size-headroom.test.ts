/**
 * risk_controller(position_size) 余量感知（2026-09-13 w-c8cae280，R-006）
 *
 * 后端 position_size 只给"账户价值×风险比"的静态建议（实测恒为 totalValue×20%、
 * accountValue 写死 100000），不看 regime 上限与当前敞口。本测试锁定新口径：
 *   可下上限 = min(单股 20% 硬顶, regime 剩余可加仓金额)
 */
import { describe, it, expect } from 'vitest';
import { RiskControllerTool } from '../packages/risk/src/tools/RiskControllerTool/RiskControllerTool';

const mkQv2 = (totalValue: number, marketValue: number, staticSize: number) => ({
  riskControl: async () => ({ command: 'position_size', result: { symbol: '600519', accountValue: 100000, recommendedSize: staticSize, maxPosition: staticSize } }),
  getPortfolioSummary: async () => ({ totalValue, totalMarketValue: marketValue }),
});

const mkMem = (regime: string, quality: string) => ({
  searchMemory: async () => ({ items: [{ status: 'active', payload: { date: '2026-09-11', regime, evidence: { data_quality: quality } } }] }),
});

const run = async (qv2: any, mem: any, args: any = {}) => {
  const tool: any = new (RiskControllerTool as any)(qv2, mem);
  return await tool.execute({ command: 'position_size', symbol: '600519', price: 1500, account_name: 'agent_brain', ...args }, {});
};

describe('risk_controller position_size 余量感知', () => {
  it('余量充足时不被余量钳制（cappedBy=single_stock_cap）', async () => {
    // 98923 × (40% - 14.2%) = 25522 > 静态 20000 → 取 20000
    const r: any = await run(mkQv2(98923, 14080, 20000), mkMem('risk_off', 'ok'));
    expect(r.result.recommendedSize).toBe(20000);
    expect(r.result.cappedBy).toBe('single_stock_cap');
    expect(r.result.regimeCapPct).toBe(40);
    expect(r.result.accountValueUsed).toBe(98923);
  });

  it('余量不足时按 regime 余量钳制（cappedBy=regime_headroom）', async () => {
    // 100000 × (40% - 35%) = 5000 < 静态 20000 → 取 5000
    const r: any = await run(mkQv2(100000, 35000, 20000), mkMem('risk_off', 'ok'));
    expect(r.result.recommendedSize).toBe(5000);
    expect(r.result.cappedBy).toBe('regime_headroom');
    expect(r.result.headroomPct).toBe(5);
  });

  it('已超限时给出 0（不鼓励继续加仓）', async () => {
    const r: any = await run(mkQv2(100000, 45000, 20000), mkMem('risk_off', 'ok'));
    expect(r.result.recommendedSize).toBe(0);
    expect(r.result.headroomPct).toBe(0);
  });

  it('数据降级时上限收紧到 60%（R-006 保守原则）', async () => {
    const r: any = await run(mkQv2(100000, 10000, 20000), mkMem('risk_on', 'degraded'));
    expect(r.result.regimeCapPct).toBe(60);
    expect(String(r.result.regimeCapNote)).toContain('收紧');
  });

  it('无 regime 记录时按震荡档 60% 并显式提示', async () => {
    const r: any = await run(mkQv2(100000, 10000, 20000), { searchMemory: async () => ({ items: [] }) });
    expect(r.result.regimeCapPct).toBe(60);
    expect(String(r.result.regimeNote)).toContain('无 regime 记录');
  });

  it('余量校验异常时降级但不阻断（保留静态建议 + 提示）', async () => {
    const bad: any = { riskControl: async () => ({ result: { recommendedSize: 20000 } }), getPortfolioSummary: async () => { throw new Error('boom'); } };
    const r: any = await run(bad, mkMem('risk_off', 'ok'));
    expect(String(r.result.headroomNote)).toContain('降级');
    expect(r.result.recommendedSize).toBe(20000);
  });
});
