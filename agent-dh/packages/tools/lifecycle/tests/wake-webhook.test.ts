import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Readable } from 'node:stream';
import { describe, expect, it, vi } from 'vitest';
import { registerWakeWebhook, WakeDedupStore } from '../src/wake-webhook.js';

function mount(options: { token?: string; maxBodyBytes?: number; dedupPath?: string; deliver?: ReturnType<typeof vi.fn> } = {}) {
  const deliver = options.deliver ?? vi.fn(async () => undefined);
  let route: any;
  const webCtx = {
    webServer: {
      register: (value: any) => {
        route = value;
        return () => undefined;
      },
    },
    effect: (fn: () => void) => fn(),
  };
  const ctx = {
    inject: (_deps: string[], fn: (value: any) => void) => fn(webCtx),
  };
  registerWakeWebhook(ctx as any, { ...options, deliver });
  return { route, deliver };
}

async function invoke(route: any, options: {
  method?: string;
  body?: string;
  headers?: Record<string, string>;
} = {}) {
  const body = options.body ?? JSON.stringify({ event: 'market_alert', data: { symbol: '600000.SH' } });
  const request: any = Readable.from([body]);
  request.method = options.method ?? 'POST';
  request.headers = {
    'content-type': 'application/json',
    ...options.headers,
  };
  const response: any = {
    status: 0,
    headers: {},
    body: '',
    setHeader(name: string, value: string) {
      this.headers[name] = value;
    },
    writeHead(status: number, headers: Record<string, string>) {
      this.status = status;
      this.headers = { ...this.headers, ...headers };
    },
    end(value: string) {
      this.body = value;
    },
  };
  await route.handler(request, response);
  return { ...response, json: JSON.parse(response.body) };
}

describe('lifecycle /wake webhook', () => {
  it('接受 V2 事件并交给投递回调', async () => {
    const { route, deliver } = mount();
    const timestamp = '2026-10-27T10:00:00Z';
    const response = await invoke(route, {
      body: JSON.stringify({ event: 'daily_report', data: { account: 'agent_brain' }, timestamp }),
    });
    expect(route.path).toBe('/wake');
    expect(response.status).toBe(200);
    expect(response.json).toMatchObject({ success: true });
    expect(response.json.event_id).toBeTruthy();
    expect(deliver).toHaveBeenCalledWith('daily_report', { account: 'agent_brain' }, timestamp);
  });

  it('拒绝非 POST 和非 JSON 请求', async () => {
    const { route, deliver } = mount();
    const wrongMethod = await invoke(route, { method: 'GET' });
    expect(wrongMethod.status).toBe(405);
    expect(wrongMethod.headers.allow).toBe('POST');
    const wrongType = await invoke(route, { headers: { 'content-type': 'text/plain' } });
    expect(wrongType.status).toBe(415);
    expect(deliver).not.toHaveBeenCalled();
  });

  it('拒绝非法 JSON、空事件名和非对象载荷', async () => {
    const { route, deliver } = mount();
    expect((await invoke(route, { body: '{' })).status).toBe(400);
    expect((await invoke(route, { body: JSON.stringify({ event: ' ' }) })).status).toBe(400);
    expect((await invoke(route, { body: '[]' })).status).toBe(400);
    expect(deliver).not.toHaveBeenCalled();
  });

  it('限制请求体大小', async () => {
    const { route, deliver } = mount({ maxBodyBytes: 32 });
    const response = await invoke(route, {
      headers: { 'content-length': '1024' },
    });
    expect(response.status).toBe(413);
    expect(deliver).not.toHaveBeenCalled();
  });

  it('配置 token 后校验 X-Wake-Token', async () => {
    const { route, deliver } = mount({ token: 'secret' });
    expect((await invoke(route)).status).toBe(401);
    expect((await invoke(route, { headers: { 'x-wake-token': 'wrong' } })).status).toBe(401);
    const accepted = await invoke(route, { headers: { 'x-wake-token': 'secret' } });
    expect(accepted.status).toBe(200);
    expect(deliver).toHaveBeenCalledTimes(1);
  });

  it('投递入队失败时返回 success:false', async () => {
    const deliver = vi.fn(async () => { throw new Error('no agent'); });
    const { route } = mount({ deliver });
    const response = await invoke(route);
    expect(response.status).toBe(200);
    expect(response.json).toMatchObject({ success: false, error: 'deliver failed' });
  });

  it('同一 watch event_id 重复投递只入队一次', async () => {
    const { route, deliver } = mount();
    const body = JSON.stringify({
      event: 'watch_trigger', event_id: 'watch_trigger:4786', data: { trigger_ids: [4786] },
    });
    const first = await invoke(route, { body });
    expect(first.json).toMatchObject({ success: true, event_id: 'watch_trigger:4786' });
    for (let i = 0; i < 20; i++) {
      const duplicate = await invoke(route, { body });
      expect(duplicate.json).toMatchObject({ success: true, deduplicated: true });
    }
    expect(deliver).toHaveBeenCalledTimes(1);
  });

  it('同事件 pending 不冒充 completed；首个真实投递失败后仍可重试', async () => {
    let rejectFirst!: (error: Error) => void;
    const gate = new Promise<void>((_resolve, reject) => { rejectFirst = reject; });
    const deliver = vi.fn()
      .mockImplementationOnce(() => gate)
      .mockResolvedValueOnce(undefined);
    const { route } = mount({ deliver });
    const body = JSON.stringify({ event: 'watch_trigger', event_id: 'watch_trigger:pending-proof', data: {} });
    const firstPromise = invoke(route, { body });
    await vi.waitFor(() => expect(deliver).toHaveBeenCalledTimes(1));
    const concurrent = await invoke(route, { body });
    expect(concurrent.status).toBe(202);
    expect(concurrent.json).toMatchObject({ success: false, in_progress: true, deduplicated: true });
    rejectFirst(new Error('first delivery failed'));
    expect((await firstPromise).json).toMatchObject({ success: false });
    expect((await invoke(route, { body })).json).toMatchObject({ success: true });
    expect(deliver).toHaveBeenCalledTimes(2);
  });

  it('入队失败释放 pending，允许同 event_id 真正重试', async () => {
    const deliver = vi.fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(undefined);
    const { route } = mount({ deliver });
    const body = JSON.stringify({ event: 'watch_trigger', event_id: 'watch_trigger:failed-1', data: {} });
    expect((await invoke(route, { body })).json).toMatchObject({ success: false });
    expect((await invoke(route, { body })).json).toMatchObject({ success: true });
    expect(deliver).toHaveBeenCalledTimes(2);
  });

  it('completed 幂等台账跨 handler 重启恢复', async () => {
    const directory = mkdtempSync(join(tmpdir(), 'wake-dedup-test-'));
    const dedupPath = join(directory, 'wake-dedup.json');
    try {
      const first = mount({ dedupPath });
      const body = JSON.stringify({ event: 'watch_trigger', event_id: 'watch_trigger:restart-1', data: {} });
      expect((await invoke(first.route, { body })).json.success).toBe(true);
      const second = mount({ dedupPath });
      expect((await invoke(second.route, { body })).json).toMatchObject({ success: true, deduplicated: true });
      expect(first.deliver).toHaveBeenCalledTimes(1);
      expect(second.deliver).not.toHaveBeenCalled();
    } finally {
      expect(directory.startsWith(join(tmpdir(), 'wake-dedup-test-'))).toBe(true);
      rmSync(directory, { recursive: true, force: true });
    }
  });

  it('合法 JSON 但结构损坏的幂等台账返回 503，不静默清空重投', async () => {
    const malformed = [
      { version: 1, entries: [] },
      { version: 1 },
      { version: 1, entries: { old: { state: 'completed' } } },
      { version: 1, entries: { old: { state: 'bad', updatedAt: 1 } } },
    ];
    for (const value of malformed) {
      const directory = mkdtempSync(join(tmpdir(), 'wake-dedup-test-'));
      const dedupPath = join(directory, 'wake-dedup.json');
      try {
        writeFileSync(dedupPath, JSON.stringify(value));
        const { route, deliver } = mount({ dedupPath });
        const response = await invoke(route);
        expect(response.status).toBe(503);
        expect(deliver).not.toHaveBeenCalled();
      } finally {
        expect(directory.startsWith(join(tmpdir(), 'wake-dedup-test-'))).toBe(true);
        rmSync(directory, { recursive: true, force: true });
      }
    }
  });

  it('reserve 持久化失败会撤销内存占位，同键可在写恢复后重试', () => {
    const store = new WakeDedupStore('');
    const persist = vi.spyOn(store as any, 'persist').mockImplementationOnce(() => {
      throw new Error('disk full');
    });
    expect(() => store.reserve('evt-reserve', 1000)).toThrow('disk full');
    persist.mockRestore();
    expect(store.reserve('evt-reserve', 1001)).toBe(true);
  });

  it('watch 事件缺稳定幂等身份时拒绝，不伪造一次性 timestamp 键', async () => {
    const { route, deliver } = mount();
    const response = await invoke(route, {
      body: JSON.stringify({ event: 'watch_trigger', data: { symbol: '600000' }, timestamp: '2026-11-18' }),
    });
    expect(response.status).toBe(400);
    expect(deliver).not.toHaveBeenCalled();
  });
});
