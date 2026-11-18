import { Readable } from 'node:stream';
import { describe, expect, it, vi } from 'vitest';
import { registerWakeWebhook } from '../src/wake-webhook.js';

function mount(options: { token?: string; maxBodyBytes?: number; deliver?: ReturnType<typeof vi.fn> } = {}) {
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
    expect(response.json).toEqual({ success: true });
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
    expect(response.json).toEqual({ success: false, error: 'deliver failed' });
  });
});
