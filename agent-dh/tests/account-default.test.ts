/**
 * 账户默认值策略测试（2026-09-13 w-c8cae280；同日按用户裁定改为"工具层默认 + 不拦截"）
 *
 * 设计（用户 2026-09-13 裁定）：
 *   ① account_name 由**工具层**给默认值：agent-dh = agent_brain（agent-ts 侧各自维护 agent_virtual）；
 *   ② **不对工具做拦截**——缺参按默认账户执行，显式传入则以传入为准；
 *   ③ 账户名**不写死在任务/提示词/代码**：事实源是 agents.json 的 instance.account，
 *      代码侧唯一常量 core-tool 的 DEFAULT_AGENT_ACCOUNT。
 *
 * 本文件的职责：锁住 ②③ 两条，并证明默认值在**真实调用链**上确实解析成实例账户。
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';

import { DEFAULT_AGENT_ACCOUNT } from '../packages/core/core-tool/src/account';
import { PortfolioTradeTool } from '../packages/tools/trading/src/tools/PortfolioTradeTool/PortfolioTradeTool';
import { AlgoExecuteTool } from '../packages/tools/trading/src/tools/AlgoExecuteTool/AlgoExecuteTool';
import { CancelPendingOrderTool } from '../packages/tools/trading/src/tools/CancelPendingOrderTool/CancelPendingOrderTool';
import { M4CircuitBreakerTool } from '../packages/tools/trading/src/tools/M4CircuitBreakerTool/M4CircuitBreakerTool';
import { RotationExecuteTool } from '../packages/tools/strategy/src/tools/RotationExecuteTool/RotationExecuteTool';

const mk = (Ctor: any) => Object.create(Ctor.prototype) as any;

const WRITE_TOOLS: Array<[string, any, any]> = [
  ['portfolio_trade', PortfolioTradeTool, { action: 'BUY', symbol: '600519', quantity: 100 }],
  ['algo_execute', AlgoExecuteTool, { action: 'BUY', symbol: '600519', quantity: 1000 }],
  ['cancel_pending_order', CancelPendingOrderTool, { order_id: 19 }],
  ['m4_circuit_breaker_check', M4CircuitBreakerTool, {}],
  ['rotation_execute', RotationExecuteTool, { proposals: [{ action: 'activate', strategy_id: 1 }] }],
];

describe('账户默认值：工具层兜底、不做拦截', () => {
  for (const [name, Ctor, base] of WRITE_TOOLS) {
    it(name + '：缺 account_name 时校验通过（不拦截）', () => {
      const res = mk(Ctor).validate({ ...base });
      expect(res.success).toBe(true);
    });

    it(name + '：显式传账户时校验通过（由调用方负责）', () => {
      expect(mk(Ctor).validate({ ...base, account_name: 'agent-ts 的账户' }).success).toBe(true);
    });
  }
});

describe('账户默认值在真实调用链上解析为实例账户', () => {
  it('cancel_pending_order 缺参 → 用 DEFAULT_AGENT_ACCOUNT 查挂单（不产生任何委托）', async () => {
    let seen: string | undefined;
    const qv2: any = {
      listPendingOrders: async (account: string) => { seen = account; return []; },
      cancelPendingOrder: async () => { throw new Error("测试不应走到撤单"); },
    };
    const tool: any = new (CancelPendingOrderTool as any)(qv2);
    const def = tool.toDSHToolDefinition();
    await expect(def.execute({ order_id: 19 })).rejects.toThrow(/pending 列表/);
    expect(seen).toBe(DEFAULT_AGENT_ACCOUNT);
  });

  it('显式传入则用传入值（不覆盖调用方）', async () => {
    let seen: string | undefined;
    const qv2: any = { listPendingOrders: async (account: string) => { seen = account; return []; } };
    const tool: any = new (CancelPendingOrderTool as any)(qv2);
    await expect(tool.toDSHToolDefinition().execute({ order_id: 19, account_name: 'some_other_book' })).rejects.toThrow();
    expect(seen).toBe('some_other_book');
  });
});

describe('账户名不得写死（源码 + dist 产物）', () => {
  const root = join(__dirname, '..');
  const walk = (dir: string, out: string[] = []): string[] => {
    if (!existsSync(dir)) return out;
    for (const e of readdirSync(dir)) {
      const f = join(dir, e);
      if (e === 'node_modules') continue;
      if (statSync(f).isDirectory()) walk(f, out);
      else if (f.endsWith('.ts') && !f.endsWith('.d.ts')) out.push(f);
    }
    return out;
  };
  const roots = [
    ...readdirSync(join(root, 'packages')).map((p) => join(root, 'packages', p, 'src')),
    join(root, '..', 'quantsys-v2-client', 'src'),
  ].filter((d) => existsSync(d));

  // 仅匹配"把 agent_virtual 当默认值/示例"，排除比较运算与归属说明注释
  const OFFEND = /(\|\||\?\?|default\s*[:=]|example\s*:)\s*'agent_virtual'|(?<![=!<>])=\s*'agent_virtual'/;

  it('src 里没有把 agent_virtual 当默认账户/示例的写法', () => {
    const bad: string[] = [];
    for (const f of roots.flatMap((r) => walk(r))) {
      for (const [i, line] of readFileSync(f, 'utf-8').split('\n').entries()) {
        if (OFFEND.test(line)) bad.push(f.replace(root + '/', '') + ':' + (i + 1) + ' ' + line.trim());
      }
    }
    expect(bad).toEqual([]);
  });

  it('dist 产物同样没有把 agent_virtual 当默认账户', () => {
    const dists = [
      join(root, '..', 'quantsys-v2-client', 'dist', 'index.mjs'),
      join(root, 'packages', 'trading', 'dist', 'index.mjs'),
      join(root, 'packages', 'risk', 'dist', 'index.mjs'),
      join(root, 'packages', 'strategy', 'dist', 'index.mjs'),
    ].filter((f) => existsSync(f));
    const bad = dists.filter((f) =>
      /(\|\||\?\?|default\s*[:=]|example\s*:)\s*"agent_virtual"|(?<![=!<>])=\s*"agent_virtual"/.test(readFileSync(f, 'utf-8')));
    expect(bad).toEqual([]);
  });

  it('默认值统一来自 DEFAULT_AGENT_ACCOUNT（抽样 4 个读工具）', () => {
    const files = [
      'trading/src/tools/AccountInfoTool/AccountInfoTool.ts',
      'trading/src/tools/PositionListTool/PositionListTool.ts',
      'risk/src/tools/RegimePositionLimitTool/RegimePositionLimitTool.ts',
      'risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts',
    ];
    for (const rel of files) {
      expect(readFileSync(join(root, 'packages', rel), 'utf-8')).toContain('|| DEFAULT_AGENT_ACCOUNT');
    }
  });
});
