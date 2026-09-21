/**
 * risk_controller(position_size) 余量感知（2026-09-13 w-c8cae280，R-006；同日晚按独立审阅 M1/M2/M3 加固）
 *
 * 后端 position_size 只给"账户价值×风险比"的静态建议（account_value 缺省是硬编码 100000），
 * 不看 regime 上限与当前敞口。新口径：
 *   可下上限 = min(单股 20% 硬顶, regime 剩余可加仓金额)（总值不可用时降级为静态建议）
 */
import { describe, it, expect } from 'vitest';
import { RiskControllerTool } from '../../../packages/tools/risk/src/tools/RiskControllerTool/RiskControllerTool';

const mkQv2 = (totalValue: number, marketValue: number, staticSize: number, backendAccountValue = 100000) => ({
  // 形状对齐线上真实返回（tsx 实测）：顶层与 result 内都有 accountValue/recommendedSize ——
  // 这正是 M2 的现场：顶层 accountValue 是后端 account_value 缺省的硬编码 100000。
  riskControl: async () => ({
    command: 'position_size',
    symbol: '600519',
    result: { symbol: '600519', accountValue: backendAccountValue, recommendedSize: staticSize, maxPosition: staticSize },
    accountValue: backendAccountValue,
    riskPercent: 2,
    recommendedSize: staticSize,
    maxPosition: staticSize,
  }),
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
    const r: any = await run(mkQv2(98923, 14080, 20000), mkMem('risk_off', 'ok'));
    expect(r.result.recommendedSize).toBe(20000);
    expect(r.result.cappedBy).toBe('single_stock_cap');
    expect(r.result.regimeCapPct).toBe(40);
    expect(r.result.accountValueUsed).toBe(98923);
  });

  it('余量不足时按 regime 余量钳制（cappedBy=regime_headroom）', async () => {
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

  it('账户总值缺失（totalValue=0）时降级为静态建议，不误标 regime 钳制（M1）', async () => {
    const r: any = await run(mkQv2(0, 0, 20000), mkMem('risk_off', 'ok'));
    expect(r.result.recommendedSize).toBe(20000);
    expect(r.result.cappedBy).toBe('account_value_unavailable');
    expect(String(r.result.headroomNote)).toContain('不可用');
  });

  it('余量校验抛异常时降级但不阻断（同样不误标 regime 钳制）', async () => {
    const bad: any = { riskControl: async () => ({ result: { recommendedSize: 20000 } }), getPortfolioSummary: async () => { throw new Error('boom'); } };
    const r: any = await run(bad, mkMem('risk_off', 'ok'));
    expect(r.result.recommendedSize).toBe(20000);
    expect(r.result.cappedBy).toBe('account_value_unavailable');
  });

  it('后端硬编码 accountValue 被真实总值覆盖并留痕（M2）', async () => {
    const r: any = await run(mkQv2(98923, 14080, 20000, 100000), mkMem('risk_off', 'ok'));
    expect(r.accountValue).toBe(98923);
    expect(r.backendAccountValueIgnored).toBe(100000);
  });

  it('返回里带 disclaimer 说明未做多笔预留（M3）', async () => {
    const r: any = await run(mkQv2(98923, 14080, 20000), mkMem('risk_off', 'ok'));
    expect(String(r.result.disclaimer)).toContain('未对同时挂出的多笔委托做预留');
  });
});
