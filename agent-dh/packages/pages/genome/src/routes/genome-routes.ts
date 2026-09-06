// @pi-investment/dashboard-genome · 路由薄层
// /dashboard/api/genome：200 {success,true,data:GenomeData}（唯一路由，client 半同源 fetch）。
// 只读聚合；host 内部异常 → 500 {success:false,error}，前端降级横幅。

import type { IncomingMessage, ServerResponse } from 'node:http'
import { GenomeAggregationService } from '../services/genome-aggregation.js'

function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body)
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  })
  res.end(text)
}

export function createGenomeHandler(aggregator: GenomeAggregationService) {
  return async (_req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const data = await aggregator.fetchGenomeData()
      json(res, 200, { success: true, data })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      json(res, 500, { success: false, error: msg })
    }
  }
}
