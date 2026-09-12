/**
 * R-019 账户边界护栏测试（2026-09-13 w-c8cae280）
 *
 * 背景：工具层把 agent_virtual（= agent-ts/fin-agent 的账户）硬编码为默认账户，
 * 导致 agent-dh 的例行任务把成交打到了别人的账上（实测 23 笔，其中 5 笔 reason
 * 引用 agent-dh 规则号）。本测试锁定两条护栏：
 *   ① 5 个写工具（portfolio_trade / algo_execute / cancel_pending_order /
 *      m4_circuit_breaker_check / rotation_execute）缺 account_name 一律拒绝；
 *   ② 显式传 agent_virtual 一律拒绝（agent-dh 只读不写）；
 *   ③ 源码里不再残留 'agent_virtual' 作为账户默认值。
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { PortfolioTradeTool } from '../packages/trading/src/tools/PortfolioTradeTool/PortfolioTradeTool';
import { AlgoExecuteTool } from '../packages/trading/src/tools/AlgoExecuteTool/AlgoExecuteTool';
import { CancelPendingOrderTool } from '../packages/trading/src/tools/CancelPendingOrderTool/CancelPendingOrderTool';
import { M4CircuitBreakerTool } from '../packages/trading/src/tools/M4CircuitBreakerTool/M4CircuitBreakerTool';
import { RotationExecuteTool } from '../packages/strategy/src/tools/RotationExecuteTool/RotationExecuteTool';

/** 用原型构造：validate 不依赖构造参数，避免为了测校验去造 qv2/osMemory 假件 */
const mk = (Ctor: any) => Object.create(Ctor.prototype) as any;

const WRITE_TOOLS: Array<[string, any, any]> = [
  ['portfolio_trade', PortfolioTradeTool, { action: 'BUY', symbol: '600519', quantity: 100 }],
  ['algo_execute', AlgoExecuteTool, { action: 'BUY', symbol: '600519', quantity: 1000 }],
  ['cancel_pending_order', CancelPendingOrderTool, { order_id: 19 }],
  ['m4_circuit_breaker_check', M4CircuitBreakerTool, {}],
  ['rotation_execute', RotationExecuteTool, { proposals: [{ action: 'activate', strategy_id: 1 }] }],
];

describe('R-019 写操作账户护栏', () => {
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

    it(name + '：account_name=agent_brain 通过', () => {
      const res = mk(Ctor).validate({ ...base, account_name: 'agent_brain' });
      expect(res.success).toBe(true);
    });
  }
});

describe('R-019 源码不得再把 agent_virtual 当默认账户', () => {
  const roots = ['trading', 'risk', 'strategy', 'intelligence'].map((p) =>
    join(__dirname, '..', 'packages', p, 'src'),
  );

  const walk = (dir: string, out: string[] = []): string[] => {
    for (const e of readdirSync(dir)) {
      const f = join(dir, e);
      if (e === 'node_modules' || e === 'dist' || e === 'lib') continue;
      if (statSync(f).isDirectory()) walk(f, out);
      else if (f.endsWith('.ts')) out.push(f);
    }
    return out;
  };

  it("代码里不存在 \"|| 'agent_virtual'\" 或 default: 'agent_virtual'", () => {
    const bad: string[] = [];
    for (const f of roots.flatMap((r) => walk(r))) {
      const text = readFileSync(f, 'utf-8');
      for (const [i, line] of text.split('\n').entries()) {
        if (/\|\|\s*'agent_virtual'/.test(line)) bad.push(f + ':' + (i + 1) + ' ' + line.trim());
        if (/default:\s*'agent_virtual'/.test(line)) bad.push(f + ':' + (i + 1) + ' ' + line.trim());
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
      const text = readFileSync(join(__dirname, '..', 'packages', rel), 'utf-8');
      expect(text).toContain("|| 'agent_brain'");
    }
  });
});
