/**
 * 全流程一览投影（REQ-47939a t6）——assembleStageOverview 的端口化查询入口。
 *
 * 与 QueryStageDetail 同源：装配逻辑单点在 QueryStageDetail（从 host/stage-detail.ts 搬入），
 * 本文件只提供"按需求 id 取台账 → 装配"的只读入口，供 HTTP 路由与会话工具调用。
 *
 * @module dsh-pmboard/application/query/QueryStageOverview
 */
import type { UseCaseDeps } from '../ports.js'
import { assembleStageOverview } from './QueryStageDetail.js'
import type { StageOverview } from '../../shared/protocol.js'

/** 某需求全流程一览（需求不存在 → 抛 not_found）。 */
export async function queryStageOverview(
  deps: UseCaseDeps,
  requirementId: string,
): Promise<StageOverview> {
  const snapshot = deps.repo.snapshot()
  const req = snapshot.requirements.find(r => r.id === requirementId)
  return assembleStageOverview(req, snapshot)
}
