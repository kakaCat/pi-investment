/**
 * Checkpoint 管理器
 * 
 * 负责写入/读取/清理 checkpoint，支持实施链的断点续传。
 * Checkpoint 存储在 RequirementRecord.advance 中。
 */

import type { Checkpoint } from '../../domain/checkpoint.js'
import type { RequirementRecord } from '../../client/types.js'

/**
 * Checkpoint 管理器
 */
export class CheckpointManager {
  /**
   * 写入 checkpoint
   * 
   * @param requirement 需求记录
   * @param checkpoint checkpoint 数据
   * @returns 更新后的 requirement（浅拷贝，advance 部分为新对象）
   */
  writeCheckpoint(requirement: RequirementRecord, checkpoint: Checkpoint): RequirementRecord {
    return {
      ...requirement,
      advance: {
        ...(requirement.advance || {}),
        runId: checkpoint.runId,
        currentSubtaskId: checkpoint.currentSubtaskId,
        stepIndex: checkpoint.stepIndex,
        heartbeatAt: checkpoint.heartbeatAt
      }
    }
  }

  /**
   * 读取 checkpoint
   * 
   * @param requirement 需求记录
   * @returns checkpoint 数据，如果没有则返回 null
   */
  readCheckpoint(requirement: RequirementRecord): Checkpoint | null {
    const advance = requirement.advance
    
    if (!advance || !advance.runId) {
      return null
    }
    
    return {
      runId: advance.runId,
      currentSubtaskId: advance.currentSubtaskId,
      stepIndex: advance.stepIndex,
      heartbeatAt: advance.heartbeatAt
    }
  }

  /**
   * 清理 checkpoint
   * 
   * @param requirement 需求记录
   * @returns 更新后的 requirement（浅拷贝，checkpoint 字段已清除）
   */
  clearCheckpoint(requirement: RequirementRecord): RequirementRecord {
    if (!requirement.advance) {
      return requirement
    }
    
    const { runId, currentSubtaskId, stepIndex, heartbeatAt, ...restAdvance } = requirement.advance
    
    return {
      ...requirement,
      advance: restAdvance
    }
  }

  /**
   * 更新心跳
   * 
   * @param requirement 需求记录
   * @returns 更新后的 requirement（heartbeatAt 更新为当前时间）
   */
  updateHeartbeat(requirement: RequirementRecord): RequirementRecord {
    if (!requirement.advance || !requirement.advance.runId) {
      // 没有运行中的 checkpoint，不更新
      return requirement
    }
    
    return {
      ...requirement,
      advance: {
        ...requirement.advance,
        heartbeatAt: Date.now()
      }
    }
  }

  /**
   * 检查 checkpoint 是否存在
   * 
   * @param requirement 需求记录
   * @returns true=有 checkpoint，false=无
   */
  hasCheckpoint(requirement: RequirementRecord): boolean {
    return !!(requirement.advance && requirement.advance.runId)
  }

  /**
   * 获取心跳年龄（距离上次心跳的时间）
   * 
   * @param requirement 需求记录
   * @returns 心跳年龄（ms），如果没有心跳则返回 null
   */
  getHeartbeatAge(requirement: RequirementRecord): number | null {
    const advance = requirement.advance
    
    if (!advance || !advance.heartbeatAt) {
      return null
    }
    
    return Date.now() - advance.heartbeatAt
  }
}

/**
 * 默认的 checkpoint 管理器实例
 */
export const checkpointManager = new CheckpointManager()
