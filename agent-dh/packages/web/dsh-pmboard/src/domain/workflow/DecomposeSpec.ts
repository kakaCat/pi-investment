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

/** 拆分幂等守卫：返回拒绝原因（ok=false）或放行（ok=true）。 */
export function checkDecomposeIdempotency(
  status: RequirementStatus,
  existingTasks: readonly ExistingTaskLike[],
): DecomposeVerdict {
  if (status === 'implementing' || status === 'accepting') {
    return {
      ok: false,
      code: 'REQBOARD_ALREADY_DECOMPOSED',
      reason: fmt('需求已处于 {status}（拆分已完成），重复拆分会产生重复任务。要调整任务请逐任务修改，或人工取消后重拆', { status }),
    }
  }
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
