/**
 * 拆分幂等规约（REQ-47939a t3 / INV-3）——decompose 的两道防线。
 *
 * 事故 B（REQ-6f39b5）：拆分成功落库后同程序内 move 被闸门拒绝 → agent 不知已拆
 * 成功，重试 decompose → 幽灵任务双倍落库、rollup 永久卡死。两道防线：
 *  ① 状态已**越过**拆分（实施/验收中）→ 说明已拆过，拒绝；
 *  ② 台账已有该需求的未取消任务 → 拒绝并返回已有清单（防状态异常时的漏网）。
 * 2026-09-17 修正（REQ-47939a 自身实测触发）：原守卫把 decomposing 也当作"已拆过"，但计划
 * 批准（reqboard_ask_confirm target=plan）会**自动**把 design → decomposing，于是正常
 * 路径必然先到 decomposing 再调 decompose → 被自己的守卫拒死，审批流水线自锁。
 * 正解：幽灵任务的唯一判据是"已有任务"（防线②），状态只用于区分"是否已越过拆分"。
 *
 * 纯函数：零 I/O、不碰时间与随机数；返回结构化原因（调用方拼 'reqboard_decompose 未执行：' 前缀）。
 */

import { fmt } from '../text/fmt.js'
import type { RequirementStatus } from '../requirement/RequirementStatus.js'

/** 已有任务的最小投影（清单提示用）。 */
export interface ExistingTaskLike {
  id: string
  title: string
  status: string
}

export type DecomposeVerdict =
  | { ok: true }
  | { ok: false; code: 'REQBOARD_ALREADY_DECOMPOSED'; reason: string }

/**
 * 拆分幂等守卫：返回拒绝原因（ok=false）或放行（ok=true）。
 *
 * 判据（2026-09-26 修正）：**唯一拒绝条件是「已有未取消任务」**。
 * 原第二条「状态已越过拆分（implementing/accepting）→ 一律拒绝」在**自动拆分失败**的
 * 既定形态下造成死锁：需求被推进到 implementing，但一条任务卡都没落库——既不能重拆
 * （本守卫拒），也不能退回上游（implementing→design 的产物门要求 task_detail 产物）。
 * 这与本守卫自己的注释一致：幽灵任务的唯一判据是「已有任务」；状态不再单独作为拒绝判据。
 * `_status` 形参保留以兼容既有调用点与类型契约。
 */
export function checkDecomposeIdempotency(
  _status: RequirementStatus,
  existingTasks: readonly ExistingTaskLike[],
): DecomposeVerdict {
  if (existingTasks.length > 0) {
    const list = existingTasks.map(t => t.id + ' ' + t.title + '（' + t.status + '）').join('；')
    return {
      ok: false,
      code: 'REQBOARD_ALREADY_DECOMPOSED',
      reason: fmt('该需求已落库 {count} 个未取消任务，禁止重复拆分。已有任务：{list}', { count: existingTasks.length, list }),
    }
  }
  return { ok: true }
}
