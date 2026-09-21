/**
 * 僵尸任务清理端点契约 — 2026-09-13 w-32314d00
 *
 * 背景：看板「清理」原来打**通用**任务删除 DELETE /scheduler/tasks/{id}，而 Agent OS 为僵尸任务
 * 提供了专用端点 DELETE /scheduler/orphaned-tasks/{id}（CleanupOrphanedTask），后者带一道安全校验：
 * 任务仍在调度器中则**拒绝删除**。用通用端点会绕过该校验——僵尸列表过期时，点「清理」会删掉
 * 一个正在调度的任务。
 *
 * 本用例锁定：①优先打专用端点；②仅旧版 Agent OS 无该路由（404）才回退通用端点；
 * ③专用端点的拒绝（如 500 + cannot delete task that is in scheduler）**不得**被回退吃掉。
 */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { Readable } from 'node:stream';
import type { IncomingMessage, ServerResponse } from 'node:http';

import { createOrphanedTaskCleanupHandler } from '../src/routes/dashboard-routes';

const TASK_ID = '1deba5ac-c4a1-459e-918c-b087d9ed7bbd';

function fakeReq(body: unknown): IncomingMessage {
  return Readable.from([Buffer.from(JSON.stringify(body))]) as unknown as IncomingMessage;
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

function stubFetch(handler: (url: string) => { status: number; body: any }) {
  const urls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (u: any) => {
    const url = String(u);
    urls.push(url);
    const { status, body } = handler(url);
    return { ok: status >= 200 && status < 300, status, json: async () => body } as any;
  }));
  return urls;
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('僵尸任务清理端点', () => {
  it('优先打 Agent OS 专用端点 orphaned-tasks', async () => {
    const urls = stubFetch(() => ({ status: 200, body: { success: true, message: 'Orphaned task deleted successfully' } }));
    const handler = createOrphanedTaskCleanupHandler({ osBaseURL: 'http://os' });
    const { res, captured } = fakeRes();
    await handler(fakeReq({ id: TASK_ID }), res);

    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain(`/api/v1/scheduler/orphaned-tasks/${TASK_ID}`);
    expect(urls[0]).not.toContain('/scheduler/tasks/');
    expect(captured.body.success).toBe(true);
    expect(captured.body.data.via).toBe('orphaned');
  });

  it('专用端点 404（旧版 Agent OS 无此路由）才回退通用端点', async () => {
    const urls = stubFetch((url) => url.includes('/orphaned-tasks/')
      ? { status: 404, body: { message: 'no route' } }
      : { status: 200, body: { message: 'task deleted successfully' } });
    const handler = createOrphanedTaskCleanupHandler({ osBaseURL: 'http://os' });
    const { res, captured } = fakeRes();
    await handler(fakeReq({ id: TASK_ID }), res);

    expect(urls).toHaveLength(2);
    expect(urls[1]).toContain(`/api/v1/scheduler/tasks/${TASK_ID}`);
    expect(captured.body.success).toBe(true);
    expect(captured.body.data.via).toBe('generic');
  });

  it('专用端点的安全拒绝（任务仍在调度器）不得被回退吃掉', async () => {
    const urls = stubFetch(() => ({
      status: 500,
      body: { message: 'failed to cleanup orphaned task: cannot delete task that is in scheduler' },
    }));
    const handler = createOrphanedTaskCleanupHandler({ osBaseURL: 'http://os' });
    const { res, captured } = fakeRes();
    await handler(fakeReq({ id: TASK_ID }), res);

    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain('/orphaned-tasks/');
    expect(captured.body.success).toBe(false);
    expect(String(captured.body.error)).toContain('in scheduler');
    expect(captured.body.via).toBe('orphaned');
  });

  it('缺 id 直接 400，不打后端', async () => {
    const urls = stubFetch(() => ({ status: 200, body: {} }));
    const handler = createOrphanedTaskCleanupHandler({ osBaseURL: 'http://os' });
    const { res, captured } = fakeRes();
    await handler(fakeReq({}), res);

    expect(urls).toHaveLength(0);
    expect(captured.status).toBe(400);
  });
});
