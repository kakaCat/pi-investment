/**
 * R-019 账户边界护栏测试（2026-09-13 w-c8cae280，2026-09-13 独立审阅后加固 M7/M8）
 *
 * 背景：工具层把 agent_virtual（= agent-ts/fin-agent 的账户）硬编码为默认账户，
 * 导致 agent-dh 的例行任务把成交打到了别人的账上（实测 23 笔，其中 5 笔 reason
 * 引用 agent-dh 规则号）。本测试锁定三层防线：
 *   ① 5 个写工具（portfolio_trade / algo_execute / cancel_pending_order /
 *      m4_circuit_breaker_check / rotation_execute）缺 account_name 一律拒绝；
 *   ② 显式传 agent_virtual（别人的账）或 default（已冻结 legacy）一律拒绝；
 *   ③ 源码与 dist 产物里都不得再把 agent_virtual 当账户默认值。
 *
 * M7 加固点（独立审阅指出）：原实现用 Object.create 只测 validate，取证面窄。
 * 现补一组走 toDSHToolDefinition().execute 的**真实调用链**断言（抛错而非返回 false）。
 */
import { describe, it, expect } from 'vitest';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { PortfolioTradeTool } from '../packages/trading/src/tools/PortfolioTradeTool/PortfolioTradeTool';
import { AlgoExecuteTool } from '../packages/trading/src/tools/AlgoExecuteTool/AlgoExecuteTool';
import { CancelPendingOrderTool } from '../packages/trading/src/tools/CancelPendingOrderTool/CancelPendingOrderTool';
import { M4CircuitBreakerTool } from '../packages/trading/src/tools/M4CircuitBreakerTool/M4CircuitBreakerTool';
import { RotationExecuteTool } from '../packages/strategy/src/tools/RotationExecuteTool/RotationExecuteTool';

/** 原型构造：只看 validate，避免为校验去造 qv2/osMemory 假件 */
const mk = (Ctor: any) => Object.create(Ctor.prototype) as any;
/** 真实例：走完整 toDSHToolDefinition().execute 链路（多传的构造参数会被忽略） */
const real = (Ctor: any) => new (Ctor as any)({}, {}, {}) as any;

const WRITE_TOOLS: Array<[string, any, any]> = [
  ['portfolio_trade', PortfolioTradeTool, { action: 'BUY', symbol: '600519', quantity: 100 }],
  ['algo_execute', AlgoExecuteTool, { action: 'BUY', symbol: '600519', quantity: 1000 }],
  ['cancel_pending_order', CancelPendingOrderTool, { order_id: 19 }],
  ['m4_circuit_breaker_check', M4CircuitBreakerTool, {}],
  ['rotation_execute', RotationExecuteTool, { proposals: [{ action: 'activate', strategy_id: 1 }] }],
];

describe('R-019 写操作账户护栏（validate 层）', () => {
  for (const [name, Ctor, base] of WRITE_TOOLS) {
    it(name + '：缺 account_name 直接拒绝', () => {
      const res = mk(Ctor).validate({ ...base });
      expect(res.success).toBe(false);
      expect(res.field).toBe('account_name');
      expect(String(res.issue)).toContain('显式传');
    });

    it(name + '：显式传 agent_virtual（agent-ts 的账）直接拒绝', () => {
      const res = mk(Ctor).validate({ ...base, account_name: 'agent_virtual' });
      expect(res.success).toBe(false);
      expect(res.field).toBe('account_name');
      expect(String(res.issue)).toContain('agent-ts');
    });

    it(name + '：显式传 default（已冻结 legacy 账户）直接拒绝', () => {
      const res = mk(Ctor).validate({ ...base, account_name: 'default' });
      expect(res.success).toBe(false);
      expect(res.field).toBe('account_name');
      expect(String(res.issue)).toContain('legacy');
    });

    it(name + '：account_name=agent_brain 通过', () => {
      const res = mk(Ctor).validate({ ...base, account_name: 'agent_brain' });
      expect(res.success).toBe(true);
    });
  }
});

describe('R-019 真实调用链（toDSHToolDefinition().execute，M7 加固）', () => {
  // 只断言"被拒"路径：通过校验的用例会真的执行下单，绝不能在测试里跑。
  for (const [name, Ctor, base] of WRITE_TOOLS) {
    it(name + '：缺参在真实链路上抛错', async () => {
      const def = real(Ctor).toDSHToolDefinition();
      await expect(def.execute({ ...base })).rejects.toThrow(/显式传 account_name/);
    });

    it(name + '：agent_virtual / default 在真实链路上抛错', async () => {
      await expect(real(Ctor).toDSHToolDefinition().execute({ ...base, account_name: 'agent_virtual' }))
        .rejects.toThrow(/agent-ts/);
      await expect(real(Ctor).toDSHToolDefinition().execute({ ...base, account_name: 'default' }))
        .rejects.toThrow(/legacy/);
    });
  }
});

describe('R-019 源码不得再把 agent_virtual 当默认账户', () => {
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
  // M7：扫描面扩到 agent-dh 全部包 + 顶层客户端（含 lib，不含 node_modules）
  const roots = [
    ...readdirSync(join(root, 'packages')).map((p) => join(root, 'packages', p, 'src')),
    join(root, '..', 'quantsys-v2-client', 'src'),
  ].filter((d) => existsSync(d));

  // 注意：必须排除比较运算（我方护栏里就有 `a === 'agent_virtual'`），否则自我误报。
  const OFFEND = /(\|\||\?\?|default\s*[:=]|example\s*:)\s*'agent_virtual'|(?<![=!<>])=\s*'agent_virtual'/;

  it('src 里不存在把 agent_virtual 当默认账户/示例的写法（宽正则）', () => {
    const bad: string[] = [];
    for (const f of roots.flatMap((r) => walk(r))) {
      for (const [i, line] of readFileSync(f, 'utf-8').split('\n').entries()) {
        if (OFFEND.test(line)) bad.push(f.replace(root + '/', '') + ':' + (i + 1) + ' ' + line.trim());
      }
    }
    expect(bad).toEqual([]);
  });

  it('dist 产物同样不得残留默认账户（顶层 client + 已构建插件）', () => {
    const dists = [
      join(root, '..', 'quantsys-v2-client', 'dist', 'index.mjs'),
      join(root, 'packages', 'trading', 'dist', 'index.mjs'),
      join(root, 'packages', 'risk', 'dist', 'index.mjs'),
      join(root, 'packages', 'strategy', 'dist', 'index.mjs'),
    ].filter((f) => existsSync(f));
    const bad: string[] = [];
    for (const f of dists) {
      const text = readFileSync(f, 'utf-8');
      if (/(\|\||\?\?|default\s*[:=]|example\s*:)\s*"agent_virtual"|(?<![=!<>])=\s*"agent_virtual"/.test(text)) {
        bad.push(f.replace(root + '/', ''));
      }
    }
    expect(bad).toEqual([]);
  });

  it('账户默认值已落到 agent_brain（抽样 4 个读工具）', () => {
    const files = [
      'trading/src/tools/AccountInfoTool/AccountInfoTool.ts',
      'trading/src/tools/PositionListTool/PositionListTool.ts',
      'risk/src/tools/RegimePositionLimitTool/RegimePositionLimitTool.ts',
      'risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts',
    ];
    for (const rel of files) {
      const text = readFileSync(join(root, 'packages', rel), 'utf-8');
      expect(text).toContain("|| 'agent_brain'");
    }
  });
});
