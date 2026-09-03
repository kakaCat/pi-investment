// 路由薄层：board JSON 信封（200 {success,data} / 500 {success:false,error}）与页面静态 HTML。
// 页面 HTML 以 import.meta.url 相对定位（tsx 直载下 __dirname 不可用），每次请求读盘（文件小，容忍热改）。

import { promises as fsp } from 'node:fs';
import { fileURLToPath } from 'node:url';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { DataAggregationService } from '../services/data-aggregation.js';
import type { BoardData } from '../types/index.js';

const pageFile = fileURLToPath(new URL('../page/execution.html', import.meta.url));

function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(text);
}

/** /dashboard/api/board：200 {success:true,data:BoardData}；部分数据源失败由 degraded 字段承载；
 *  整体失败（如内部未捕获异常）→ 500 {success:false,error}，前端据此降级为缓存+陈旧横幅 */
export function createBoardHandler(aggregator: DataAggregationService) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const data: BoardData = await aggregator.fetchBoardData();
      json(res, 200, { success: true, data });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      json(res, 500, { success: false, error: msg });
    }
  };
}

/** /dashboard/execution：自包含静态页面（内联 CSS/JS） */
export function createExecutionPageHandler() {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const html = await fsp.readFile(pageFile, 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(html);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      res.writeHead(500, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end('<html><body><h1>Execution page unavailable</h1><pre>' + escapeHtml(msg) + '</pre></body></html>');
    }
  };
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
