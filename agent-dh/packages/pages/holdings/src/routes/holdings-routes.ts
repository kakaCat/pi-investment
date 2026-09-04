// 路由薄层：holdings JSON 信封（200 {success,data} / 500 {success:false,error}）。
// 仅此一路——GUI 呈现由 client 半（lib/client.js，同源 fetch 本端点）负责，
// 不再提供独立 HTML 页面（用户纠正：HTML 页面非标准做法，标准是双半插件）。

import type { IncomingMessage, ServerResponse } from 'node:http';
import { PortfolioAggregationService } from '../services/portfolio-aggregation.js';
import type { HoldingsData } from '../types/index.js';

function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(text);
}

/** /dashboard/api/holdings：200 {success:true,data:HoldingsData}；部分数据源失败由降级处理；
 *  整体失败（如内部未捕获异常）→ 500 {success:false,error}，前端据此降级为缓存+陈旧横幅 */
export function createHoldingsHandler(aggregator: PortfolioAggregationService) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      // 解析 query 参数 account（默认 agent_virtual）
      const url = new URL(req.url || '/', `http://${req.headers.host}`);
      const account = url.searchParams.get('account') || 'agent_virtual';

      const data: HoldingsData = await aggregator.aggregate(account);
      json(res, 200, { success: true, data });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      json(res, 500, { success: false, error: msg });
    }
  };
}
