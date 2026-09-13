/**
 * strategy_list 契约测试（2026-09-13 w-a9ec14d7）
 *
 * 背景（真实故障）：StrategyListTool 用**位置参数**调用 client.listStrategies(args.source, args.code_type)，
 * 而该方法签名是**对象参数** → 传 source 即发出畸形请求 → 后端 400 → 被错误包装成「quantsys-v2 不可达」，
 * 现场表现为"工具不能调用"，极易误诊为后端进程挂了（实际后端一直健康）。
 *
 * 本文件锁住三条，防止同类误用再犯：
 *   ① 工具必须传对象（不是字符串）给 listStrategies；
 *   ② client 对非对象参数**显式抛错**（不静默发畸形请求）；
 *   ③ code_type 必须映射成后端认的 codeType。
 */
import { describe, it, expect } from 'vitest';
import { StrategyListTool } from '../packages/investment/src/tools/StrategyListTool/StrategyListTool';
import { QuantsysV2Client } from '../../quantsys-v2-client/src/client';

describe('strategy_list 契约', () => {
  it('① 工具以对象参数调用 listStrategies（回归：位置参数曾导致 400）', async () => {
    const calls: any[] = [];
    const stub = {
      listStrategies: async (params?: any) => {
        calls.push(params);
        return { total: 0, items: [] };
      },
    };
    const tool: any = Object.create(StrategyListTool.prototype);
    (tool as any).qv2 = stub;
    await tool.execute({ source: 'builtin', code_type: 'indicator' }, {} as any);
    expect(calls).toHaveLength(1);
    expect(typeof calls[0]).toBe('object');
    expect(calls[0]).toEqual({ source: 'builtin', code_type: 'indicator' });
  });

  it('② client 对非对象参数显式抛错，而不是发出畸形请求', async () => {
    const c: any = new QuantsysV2Client({ baseURL: 'http://127.0.0.1:9' } as any);
    await expect(c.listStrategies('user')).rejects.toThrow(/参数必须是对象/);
    await expect(c.listStrategies(null)).rejects.toThrow(/参数必须是对象/);
  });

  it('③ code_type 映射为后端 query 名 codeType（其余参数原样透传）', async () => {
    const c: any = new QuantsysV2Client({ baseURL: 'http://127.0.0.1:9' } as any);
    let seen: any = null;
    (c as any).client = { get: async (_u: string, cfg: any) => { seen = cfg.params; return { data: { success: true, data: { total: 0, items: [] } } }; } };
    await c.listStrategies({ source: 'user', code_type: 'indicator', page: 2 });
    expect(seen).toEqual({ source: 'user', page: 2, codeType: 'indicator' });
  });
});