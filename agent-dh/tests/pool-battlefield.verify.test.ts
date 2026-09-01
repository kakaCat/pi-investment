/**
 * M2-3 PoolBattlefieldTool 端到端验证（真实后端，2026-09-01）
 * 三条路径：pool_id 直查 / pool_name 模糊匹配 / validate 参数拒绝
 */
import { describe, expect, it } from 'vitest';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { PoolBattlefieldTool } from '../packages/competition/src/index.js';

const qv2 = new QuantsysV2Client({ baseURL: 'http://localhost:5001', timeout: 30000 });

describe('PoolBattlefieldTool（真实后端）', () => {
  it('pool_id 直查返回完整结构', async () => {
    const tool = new PoolBattlefieldTool(qv2);
    const r: any = await (tool as any).execute({ pool_id: 35 }, {} as any);
    expect(r.pool_id).toBe(35);
    expect(typeof r.battlefield_score).toBe('number');
    expect(r.opponent_strength.retail_pressure).toBeTruthy();
    expect(r.opponent_strength.institution_interest).toBeTruthy();
    expect(r.opponent_strength.hot_money_risk).toBeTruthy();
    expect(r.game_phase).toBeTruthy();
    expect(Array.isArray(r.advantages)).toBe(true);
    expect(Array.isArray(r.disadvantages)).toBe(true);
    expect(['increase', 'hold', 'reduce', 'exit']).toContain(r.recommendation);
    expect(r.confidence).toBeGreaterThan(0);
    expect(r.data_quality).toBeTruthy();
  }, 45000);

  it('pool_name 模糊匹配解析为 pool_id', async () => {
    const tool = new PoolBattlefieldTool(qv2);
    const pools: any = await qv2.listPools();
    expect(pools.length).toBeGreaterThan(0);
    const target = pools[0];
    const r: any = await (tool as any).execute({ pool_name: target.name }, {} as any);
    expect(r.pool_id).toBe(target.id);
    expect(r.pool_name).toBe(target.name);
    expect(typeof r.battlefield_score).toBe('number');
  }, 45000);

  it('validate 拒绝空参数', () => {
    const tool = new PoolBattlefieldTool(qv2);
    const v: any = (tool as any).validate({});
    expect(v.success).toBe(false);
  });

  it('pool_name 无匹配时报可读错误', async () => {
    const tool = new PoolBattlefieldTool(qv2);
    await expect(
      (tool as any).execute({ pool_name: '绝不存在的池子xyz' }, {} as any)
    ).rejects.toThrow('未找到');
  }, 30000);
});
