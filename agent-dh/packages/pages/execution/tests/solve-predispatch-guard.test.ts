/**
 * 「我来解决」派单前终态复核回归 — 2026-09-13 w-32314d00
 *
 * 背景：同一根因的卡片被重复派单 4 次（e22c1dc2 / a6c6b882 / 63fe9c5b / 1b541ee2 / d03cc5c8
 * 同属一类），其中两条投递到达时事件早已 resolved —— 处置窗口每次都要重新核验一遍状态，
 * 纯噪声。现于派单边界加一道复核：事件当前为 resolved/ignored → 直接拒单；
 * 查不到 / 查询异常 → 放行（fail-open，宁多派不误拦）。
 */
import { EventEmitter } from 'node:events';

import { describe, expect, it, vi, afterEach } from 'vitest';

import { createSolveHandler } from '@pi-investment/solve-kit';

const EV_ID = '63fe9c5b-98db-4822-a8ce-4d8920c0fdb0';

function fakeReq(body: unknown): any {
  const em = new EventEmitter() as any;
  queueMicrotask(() => {
    em.emit('data', JSON.stringify(body));
    em.emit('end');
  });
  return em;
}

function fakeRes(): any {
  const out: { status?: number; body?: any } = {};
  return {
    writeHead: (code: number) => { out.status = code; },
    end: (text: string) => { out.body = JSON.parse(text); },
    out,
  };
}

function deps(agent: any) {
  const resolveAgent = vi.fn(() => ({ agent, sessionId: 'session-32314d00', window: 'w-32314d00' }));
  return { resolveAgent };
}

const OPTS = {
  panel: '执行看板', panelFull: '双线执行确认看板', plugin: 'dashboard-execution',
  osBaseURL: 'http://127.0.0.1:8080', watchDelaysMin: [] as number[],
};

const ERR_SNAP = { id: EV_ID, source: 'v2', msg: 'boom', status: 'open', occurrenceCount: 3 };

afterEach(() => { vi.unstubAllGlobals(); });

function stubStatus(status: string | null) {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    json: async () => ({ events: status === null ? [] : [{ id: EV_ID, status }] }),
  })));
}

describe('solve 派单前终态复核', () => {
  it('已 resolved → 拒单，不投递、不解析目标会话', async () => {
    stubStatus('resolved');
    const followup = vi.fn();
    const d = deps({ followup });
    const res = fakeRes();
    await createSolveHandler(d as any, OPTS as any)(fakeReq({ kind: 'error', err: ERR_SNAP }), res);
    expect(res.out.body.success).toBe(false);
    expect(String(res.out.body.error)).toContain('已闭环');
    expect(d.resolveAgent).not.toHaveBeenCalled();
    expect(followup).not.toHaveBeenCalled();
  });

  it('已 ignored → 同样拒单', async () => {
    stubStatus('ignored');
    const followup = vi.fn();
    const res = fakeRes();
    await createSolveHandler(deps({ followup }) as any, OPTS as any)(fakeReq({ kind: 'error', err: ERR_SNAP }), res);
    expect(res.out.body.success).toBe(false);
    expect(followup).not.toHaveBeenCalled();
  });

  it('仍 open → 正常派单（回归：不能把正常派单拦掉）', async () => {
    stubStatus('open');
    const followup = vi.fn();
    const res = fakeRes();
    await createSolveHandler(deps({ followup }) as any, OPTS as any)(fakeReq({ kind: 'error', err: ERR_SNAP }), res);
    expect(res.out.body.success).toBe(true);
    expect(followup).toHaveBeenCalledTimes(1);
  });

  it('状态查询异常 → 放行（fail-open）', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('agent-os down'); }));
    const followup = vi.fn();
    const res = fakeRes();
    await createSolveHandler(deps({ followup }) as any, OPTS as any)(fakeReq({ kind: 'error', err: ERR_SNAP }), res);
    expect(res.out.body.success).toBe(true);
    expect(followup).toHaveBeenCalledTimes(1);
  });

  it('事件不在列表（查不到）→ 放行（不能当终态）', async () => {
    stubStatus(null);
    const followup = vi.fn();
    const res = fakeRes();
    await createSolveHandler(deps({ followup }) as any, OPTS as any)(fakeReq({ kind: 'error', err: ERR_SNAP }), res);
    expect(res.out.body.success).toBe(true);
    expect(followup).toHaveBeenCalledTimes(1);
  });
});
