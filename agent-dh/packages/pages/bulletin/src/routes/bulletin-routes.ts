// 路由薄层：bulletin JSON 信封（200 {success,data} / 500 {success:false,error}）。
// 仅此一路（/dashboard/api/bulletin/posts 的唯一所有者——execution 独占 /dashboard/api/board、
// holdings 独占 /dashboard/api/holdings，路由契约互斥）。GUI 呈现由 client 半负责。

import type { IncomingMessage, ServerResponse } from 'node:http'
import { BulletinAggregationService } from '../services/bulletin-aggregation.js'
import type { BulletinData, BulletinQuery } from '../types/index.js'

function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body)
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  })
  res.end(text)
}

/** GET /dashboard/api/bulletin/posts：200 {success:true,data}；降级（Agent OS 不可达）由聚合层
 *  产出 degraded:true 空数据；仅未预期异常 → 500 {success:false,error} */
export function createBulletinHandler(aggregator: BulletinAggregationService) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const url = new URL(req.url || '/', 'http://' + (req.headers.host ?? 'localhost'))
      const q = url.searchParams
      const query: BulletinQuery = {
        status: q.get('status') || undefined,
        kind: q.get('kind') || undefined,
        assignee: q.get('assignee') || undefined,
        page: q.get('page') ? Number(q.get('page')) : undefined,
        page_size: q.get('page_size') ? Number(q.get('page_size')) : undefined,
      }
      const data: BulletinData = await aggregator.fetchBulletin(query)
      json(res, 200, { success: true, data })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      json(res, 500, { success: false, error: msg })
    }
  }
}
