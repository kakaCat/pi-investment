// 路由薄层：board JSON 信封（200 {success,data} / 500 {success:false,error}）。
// 两路：GET /dashboard/api/board = 看板数据聚合；POST /dashboard/api/board/error-action = 错误事件处置代理
// （PATCH → Agent OS error_events 状态机）。GUI 呈现由 client 半（lib/client.js，同源 fetch 本端点）负责，
// 不再提供独立 HTML 页面（用户纠正：HTML 页面非标准做法，标准是双半插件）。

import type { IncomingMessage, ServerResponse } from 'node:http';
import { DataAggregationService } from '../services/data-aggregation.js';
import type { BoardData } from '../types/index.js';

function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(text);
}

function readBody(req: IncomingMessage, maxBytes = 64 * 1024): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let size = 0;
    req.on('data', (c: Buffer) => {
      size += c.length;
      if (size > maxBytes) {
        reject(new Error('body too large'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    req.on('error', reject);
  });
}

/** /dashboard/api/board：200 {success:true,data:BoardData}；部分数据源失败由 degraded 字段承载；
 *  整体失败（如内部未捕获异常）→ 500 {success:false,error}，前端据此降级为缓存+陈旧横幅 */
export function createBoardHandler(aggregator: DataAggregationService) {
  return async (_req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const data: BoardData = await aggregator.fetchBoardData();
      json(res, 200, { success: true, data });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      json(res, 500, { success: false, error: msg });
    }
  };
}

type ErrorAction = 'claim' | 'resolve' | 'ignore' | 'reopen';
const ACTION_ZH: Record<ErrorAction, string> = {
  claim: '已认领（处理中）',
  resolve: '已标记解决',
  ignore: '已忽略',
  reopen: '已复开（回到待处理）',
};

/** POST /dashboard/api/board/error-action：错误事件处置代理。
 *  body: { id, action: claim|resolve|ignore|reopen, note?, from_session? }
 *  actor = windowCode(from_session)（与 /solve 同口径：session- 前缀取中段 8 位 → w-xxxx），
 *  claim 语义 = 认领并标记处理中（assignee=操作窗口）；resolve/ignore/reopen 直接流转。
 *  信封：200 {success,data:{message,event}}；失败 200 {success:false,error}（透传 Agent OS 409 中文提示）。 */
export function createErrorActionHandler(opts: { osBaseURL: string; windowCode: (id: string) => string }) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const raw = await readBody(req);
      let parsed: any;
      try {
        parsed = raw ? JSON.parse(raw) : {};
      } catch {
        json(res, 400, { success: false, error: '请求体非合法 JSON' });
        return;
      }
      const id = parsed && parsed.id != null ? String(parsed.id) : '';
      const action = parsed && parsed.action ? String(parsed.action) : '';
      if (!id || !(action in ACTION_ZH)) {
        json(res, 400, { success: false, error: '缺少 id 或 action 非法（claim/resolve/ignore/reopen）' });
        return;
      }
      const fromSession = parsed && parsed.from_session ? String(parsed.from_session) : '';
      const actor = fromSession ? opts.windowCode(fromSession) : '';
      const note = parsed && typeof parsed.note === 'string' && parsed.note ? parsed.note : undefined;
      const resp = await fetch(
        `${opts.osBaseURL}/api/v1/scheduler/error-events/${encodeURIComponent(id)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, actor, session: fromSession || undefined, note }),
          signal: AbortSignal.timeout(4000),
        },
      );
      let data: any = {};
      try { data = await resp.json(); } catch { /* 非 JSON 响应 */ }
      if (!resp.ok || data?.success === false) {
        json(res, 200, { success: false, error: data?.message || data?.error || `HTTP ${resp.status}` });
        return;
      }
      const message = (typeof data?.message === 'string' && data.message)
        ? data.message
        : ACTION_ZH[action as ErrorAction];
      json(res, 200, { success: true, data: { message, event: data?.event ?? null } });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      json(res, 500, { success: false, error: msg });
    }
  };
}
