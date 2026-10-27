// 路由薄层：holdings JSON 信封（200 {success,data,meta?} / 503 core 不可用 / 500 未捕获异常）。
// 仅此一路——GUI 呈现由 client 半（lib/client.js，同源 fetch 本端点）负责，
// 不再提供独立 HTML 页面（用户纠正：HTML 页面非标准做法，标准是双半插件）。

import type { IncomingMessage, ServerResponse } from 'node:http';
import { CoreDataUnavailableError, PortfolioAggregationService } from '../services/portfolio-aggregation.js';
import { parseParts } from '../services/parts.js';

function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(text);
}

/** /dashboard/api/holdings：200 {success:true,data,meta?}；分块降级由聚合层处理（meta.errors 按块记录）；
 *  core（账户状态）不可用 → 503 {success:false,error,error_code,retryable}（RFC 017 P0：
 *  2026-10-26 事故的假空数据修复——超时不再返回空持仓/零摘要冒充成功）；
 *  整体失败（内部未捕获异常）→ 500 {success:false,error} */
export function createHoldingsHandler(aggregator: PortfolioAggregationService) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      // 解析 query 参数 account（默认 agent_brain）
      const url = new URL(req.url || '/', `http://${req.headers.host}`);
      const account = url.searchParams.get('account') || 'agent_brain';
      // 2026-09-13（w-adb088f2）：parts 缺省＝全量（向后兼容）；轮询用 parts=hot 只拉约 4 KB 高频块
      const parts = parseParts(url.searchParams.get('parts'));

      const { data, meta } = await aggregator.aggregate(account, { parts });
      json(res, 200, { success: true, data, meta });
    } catch (err) {
      if (err instanceof CoreDataUnavailableError) {
        json(res, 503, {
          success: false,
          error: err.message,
          error_code: err.code,
          retryable: true,
        });
        return;
      }
      const msg = err instanceof Error ? err.message : String(err);
      json(res, 500, { success: false, error: msg });
    }
  };
}

/** POST /dashboard/api/holdings/refresh?account=<name>：代理 v2 行情刷新命令（RFC 017 P2）。
 *  浏览器只与 :13080 同源通信；刷新是后台命令（v2 返回 202 + single-flight），
 *  不改变任何交易状态。失败返回 502，前端只记日志不打断看板。 */
export function createHoldingsRefreshHandler(aggregator: PortfolioAggregationService) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const url = new URL(req.url || '/', `http://${req.headers.host}`);
      const account = url.searchParams.get('account') || 'agent_brain';
      const result = await aggregator.requestQuoteRefresh(account);
      json(res, result.ok ? result.status : 502, result.body ?? { success: result.ok, error: 'empty upstream body' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      json(res, 502, { success: false, error: msg });
    }
  };
}
