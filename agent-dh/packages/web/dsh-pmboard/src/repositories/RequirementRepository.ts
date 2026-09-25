/**
 * RequirementRepository
 * 
 * 需求仓储：提供运行态读写方法（checkpoint 管理）。
 */

import type { RequirementRecord } from '../client/types.js'
import type { Checkpoint } from '../domain/checkpoint.js'

/**
 * 需求仓储接口
 */
export interface RequirementRepository {
  /**
   * 更新运行状态
   * 
   * @param reqId 需求ID
   * @param runState 运行状态
   */
  updateRunState(reqId: string, runState: {
    runId?: string
    stepIndex?: number
    currentSubtaskId?: string
    heartbeatAt?: number
  }): Promise<void>
  
  /**
   * 读取 checkpoint
   * 
   * @param reqId 需求ID
   * @returns checkpoint 或 null
   */
  readCheckpoint(reqId: string): Promise<Checkpoint | null>
  
  /**
   * 清理 checkpoint
   * 
   * @param reqId 需求ID
   */
  clearCheckpoint(reqId: string): Promise<void>
  
  /**
   * 获取需求记录
   * 
   * @param reqId 需求ID
   * @returns 需求记录或 null
   */
  getRequirement(reqId: string): Promise<RequirementRecord | null>
  
  /**
   * 更新需求记录
   * 
   * @param requirement 需求记录
   */
  updateRequirement(requirement: RequirementRecord): Promise<void>
}

/**
 * 内存实现（用于测试和简单场景）
 */
export class InMemoryRequirementRepository implements RequirementRepository {
  private requirements = new Map<string, RequirementRecord>()
  
  async updateRunState(reqId: string, runState: {
    runId?: string
    stepIndex?: number
    currentSubtaskId?: string
    heartbeatAt?: number
  }): Promise<void> {
    const req = this.requirements.get(reqId)
    if (!req) {
      throw new Error(`Requirement ${reqId} not found`)
    }
    
    this.requirements.set(reqId, {
      ...req,
      advance: {
        ...(req.advance || {}),
        ...runState
      }
    })
  }
  
  async readCheckpoint(reqId: string): Promise<Checkpoint | null> {
    const req = this.requirements.get(reqId)
    if (!req || !req.advance || !req.advance.runId) {
      return null
    }
    
    return {
      runId: req.advance.runId,
      currentSubtaskId: req.advance.currentSubtaskId,
      stepIndex: req.advance.stepIndex,
      heartbeatAt: req.advance.heartbeatAt
    }
  }
  
  async clearCheckpoint(reqId: string): Promise<void> {
    const req = this.requirements.get(reqId)
    if (!req || !req.advance) {
      return
    }
    
    const { runId, currentSubtaskId, stepIndex, heartbeatAt, ...restAdvance } = req.advance
    
    this.requirements.set(reqId, {
      ...req,
      advance: restAdvance
    })
  }
  
  async getRequirement(reqId: string): Promise<RequirementRecord | null> {
    return this.requirements.get(reqId) || null
  }
  
  async updateRequirement(requirement: RequirementRecord): Promise<void> {
    this.requirements.set(requirement.id, requirement)
  }
  
  // 测试辅助方法
  seed(requirement: RequirementRecord): void {
    this.requirements.set(requirement.id, requirement)
  }
  
  clear(): void {
    this.requirements.clear()
  }
}
