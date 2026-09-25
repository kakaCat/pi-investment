/**
 * 孤儿回收器
 * 
 * 识别超时且无活跃执行的 in_progress 子卡，将其退回 todo 或 resume。
 * 孤儿定义：status=in_progress 且心跳超时（无活跃 job）
 */

import type { TaskRecord } from '../../client/types.js'
import { LIMITS } from '../../domain/limits.js'

/**
 * 孤儿识别结果
 */
export interface OrphanResult {
  /** 孤儿任务ID列表 */
  orphanIds: string[]
  /** 识别时间 */
  identifiedAt: number
  /** 使用的超时阈值（ms） */
  thresholdMs: number
}

/**
 * 识别孤儿任务
 * 
 * @param tasks 任务列表
 * @param activeJobIds 当前活跃的 job ID 集合
 * @param thresholdMs 超时阈值（默认使用 LIMITS.orphanTimeoutMs）
 * @returns 孤儿识别结果
 */
export function identifyOrphans(
  tasks: TaskRecord[],
  activeJobIds: Set<string>,
  thresholdMs: number = LIMITS.orphanTimeoutMs
): OrphanResult {
  const now = Date.now()
  const orphanIds: string[] = []
  
  for (const task of tasks) {
    // 只检查 in_progress 状态的任务
    if (task.status !== 'in_progress') {
      continue
    }
    
    // 检查是否有活跃 job（通过 RequirementRecord.advance.runId 关联）
    // 这里简化：如果任务有 runId 且在 activeJobIds 中，则认为有活跃执行
    const hasActiveJob = task.parentId ? 
      false : // 子卡暂不支持独立 runId，由父卡管理
      false   // TODO: 从 RequirementRecord.advance.runId 读取
    
    if (hasActiveJob) {
      continue
    }
    
    // 检查心跳超时
    // 从 executions 中找最近一次 in_progress 的 startedAt
    const executions = (task as any).executions || []
    const latestExec = executions
      .filter((e: any) => e.outcome === 'running')
      .sort((a: any, b: any) => b.startedAt - a.startedAt)[0]
    
    if (!latestExec) {
      // 没有执行记录但状态是 in_progress，可能是数据异常，也视为孤儿
      orphanIds.push(task.id)
      continue
    }
    
    const heartbeatAge = now - latestExec.startedAt
    if (heartbeatAge > thresholdMs) {
      orphanIds.push(task.id)
    }
  }
  
  return {
    orphanIds,
    identifiedAt: now,
    thresholdMs
  }
}

/**
 * 判断单个任务是否为孤儿
 * 
 * @param task 任务
 * @param activeJobIds 活跃 job ID 集合
 * @param thresholdMs 超时阈值
 * @returns true=孤儿，false=正常
 */
export function isOrphan(
  task: TaskRecord,
  activeJobIds: Set<string>,
  thresholdMs: number = LIMITS.orphanTimeoutMs
): boolean {
  if (task.status !== 'in_progress') {
    return false
  }
  
  // 简化实现：检查最近执行的心跳
  const executions = (task as any).executions || []
  const latestExec = executions
    .filter((e: any) => e.outcome === 'running')
    .sort((a: any, b: any) => b.startedAt - a.startedAt)[0]
  
  if (!latestExec) {
    return true // 无执行记录视为孤儿
  }
  
  const now = Date.now()
  const heartbeatAge = now - latestExec.startedAt
  
  return heartbeatAge > thresholdMs
}

/**
 * 计算孤儿任务的重试次数
 * 
 * @param task 任务
 * @returns 重试次数（attempt + 1）
 */
export function calculateRetryAttempt(task: TaskRecord): number {
  return (task.attempt || 0) + 1
}
