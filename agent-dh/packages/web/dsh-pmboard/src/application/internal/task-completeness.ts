/**
 * 阶段推进的任务完整性判定（REQ-260927100007-b8ba FR-3）——跨状态机完整性约束的**唯一实现处**。
 *
 * 只拦"计划有卡却一张没落库"这一确定异常；正常空计划（迁移/回填/纯文档需求）不拦。
 *
 * @module dsh-pmboard/application/internal/task-completeness
 */
import type { RequirementRecord, TaskRecord } from '../../shared/protocol.js'
import { fmt } from '../../domain/text/fmt.js'

/** 缺口文案（undefined = 放行）。仅对目标态 implementing 生效。 */
export function taskCompletenessGap(
  req: RequirementRecord,
  tasks: readonly TaskRecord[],
  to: string,
): string | undefined {
  if (to !== 'implementing') return undefined
  // 存量/直种需求（无产物簿）豁免——与本仓既有 isLegacy 口径一致
  if (req.artifacts === undefined || req.artifacts.length === 0) return undefined
  const planTasks = req.plan?.tasks ?? []
  if (planTasks.length === 0) return undefined
  const live = tasks.filter(t => t.requirementId === req.id && t.status !== 'canceled')
  if (live.length > 0) return undefined
  return fmt(
    '计划有 {n} 张任务卡、台账 0 张未取消任务——拆分尚未落库，拒绝进入实施。'
    + '补齐：调 reqboard_decompose(requirement_id="{id}") 落库（或在看板点「拆分」）后重试',
    { n: planTasks.length, id: req.id },
  )
}
