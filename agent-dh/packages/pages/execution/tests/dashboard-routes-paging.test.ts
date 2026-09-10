/**
 * 看板错误事件分页参数口径回归 — 2026-09-11 w-8f2c4cc5
 *
 * 背景：handler 只认 page/pageSize，传 limit/offset 时静默回落默认分页（HTTP 200 且无提示），
 * 按 REST 惯例调用的一方因此误判「分页失效（296 条历史只能看到最新 10 条）」并据此写了错误结论。
 * 本用例锁定：两种参数名都能真正改写到 Agent OS 的 limit/offset，且响应标出采用口径。
 */
import { describe, expect, it, vi, afterEach } from 'vitest';
import type { IncomingMessage, ServerResponse } from 'node:http';

import { createErrorEventsHandler } from '../src/routes/dashboard-routes';

function fakeReq(url: string): IncomingMessage {
  return { url } as unknown as IncomingMessage;
}

function fakeRes() {
  const captured: { status?: number; body?: any } = {};
  const res = {
    writeHead: (status: number) => { captured.status = status; return res; },
    end: (payload: string) => { captured.body = JSON.parse(payload); return res; },
    setHeader: () => res,
  } as unknown as ServerResponse;
  return { res, captured };
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('看板错误事件分页参数', () => {
  it('page/pageSize 映射为 Agent OS 的 limit/offset', async () => {
    const urls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (u: any) => {
      urls.push(String(u));
      return { ok: true, status: 200, json: async () => ({ events: [], total: 296 }) } as any;
    }));
    const handler = createErrorEventsHandler({ osBaseURL: 'http://os' });
    const { res, captured } = fakeRes();
    await handler(fakeReq('/dashboard/api/board/error-events?page=3&pageSize=20'), res);

    const listUrl = urls.find((u) => u.includes('/error-events?'))!;
    expect(listUrl).toContain('limit=20');
    expect(listUrl).toContain('offset=40');
    expect(captured.body.data.page).toBe(3);
    expect(captured.body.data.paging.via).toBe('page/pageSize');
  });

  it('limit/offset 别名同样生效（此前被静默忽略）', async () => {
    const urls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (u: any) => {
      urls.push(String(u));
      return { ok: true, status: 200, json: async () => ({ events: [], total: 296 }) } as any;
    }));
    const handler = createErrorEventsHandler({ osBaseURL: 'http://os' });
    const { res, captured } = fakeRes();
    await handler(fakeReq('/dashboard/api/board/error-events?limit=3&offset=7'), res);

    const listUrl = urls.find((u) => u.includes('/error-events?'))!;
    expect(listUrl).toContain('limit=3');
    expect(listUrl).toContain('offset=7');
    expect(captured.body.data.pageSize).toBe(3);
    expect(captured.body.data.paging).toEqual({ via: 'limit/offset', offset: 7 });
  });

  it('pageSize 上限 100，非法值回落默认', async () => {
    const urls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (u: any) => {
      urls.push(String(u));
      return { ok: true, status: 200, json: async () => ({ events: [], total: 0 }) } as any;
    }));
    const handler = createErrorEventsHandler({ osBaseURL: 'http://os' });
    for (const q of ['pageSize=9999', 'pageSize=abc']) {
      const { res } = fakeRes();
      await handler(fakeReq('/dashboard/api/board/error-events?' + q), res);
    }
    expect(urls.filter((u) => u.includes('/error-events?')).map((u) => new URL(u).searchParams.get('limit')))
      .toEqual(['100', '10']);
  });
});
