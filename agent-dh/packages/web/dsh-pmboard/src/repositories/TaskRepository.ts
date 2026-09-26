/**
 * TaskRepository
 * 
 * 任务仓储：提供批量查询、状态更新、孤儿检测等方法。
 */

import type { TaskRecord } from '../client/types.js'
import { LIMITS } from '../domain/limits.js'

/**
 * 任务仓储接口
 */
export interface TaskRepository {
  /**
   * 获取需求下的所有任务
   * 
   * @param reqId 需求ID
   * @returns 任务列表
   */
  getTasksByRequirement(reqId: string): Promise<TaskRecord[]>
  
  /**
   * 获取孤儿任务
   * 
   * @param reqId 需求ID
   * @param thresholdMs 超时阈值（默认使用 LIMITS.orphanTimeoutMs）
   * @returns 孤儿任务列表
   */
  getOrphans(reqId: string, thresholdMs?: number): Promise<TaskRecord[]>
  
  /**
   * 更新心跳
   * 
   * @param taskId 任务ID
   * @param timestamp 时间戳
   */
  updateHeartbeat(taskId: string, timestamp: number): Promise<void>
  
  /**
   * 获取单个任务
   * 
   * @param taskId 任务ID
   * @returns 任务记录或 null
   */
  getTask(taskId: string): Promise<TaskRecord | null>
  
  /**
   * 更新任务
   * 
   * @param task 任务记录
   */
  updateTask(task: TaskRecord): Promise<void>
}

/**
 * 内存实现（用于测试和简单场景）
 */
export class InMemoryTaskRepository implements TaskRepository {
  private tasks = new Map<string, TaskRecord>()
  
  async getTasksByRequirement(reqId: string): Promise<TaskRecord[]> {
    return Array.from(this.tasks.values())
      .filter(task => task.requirementId === reqId)
  }
  
  async getOrphans(reqId: string, thresholdMs: number = LIMITS.orphanTimeoutMs): Promise<TaskRecord[]> {
    const tasks = await this.getTasksByRequirement(reqId)
    const now = Date.now()
    const orphans: TaskRecord[] = []
    
    for (const task of tasks) {
      // 只检查 in_progress 状态
      if (task.status !== 'in_progress') {
        continue
      }
      
      // 检查心跳
      const executions = (task as any).executions || []
      const latestExec = executions
        .filter((e: any) => e.outcome === 'running')
        .sort((a: any, b: any) => b.startedAt - a.startedAt)[0]
      
      if (!latestExec) {
        orphans.push(task)
        continue
      }
      
      const heartbeatAge = now - latestExec.startedAt
      if (heartbeatAge > thresholdMs) {
        orphans.push(task)
      }
    }
    
    return orphans
  }
  
  async updateHeartbeat(taskId: string, timestamp: number): Promise<void> {
    const task = this.tasks.get(taskId)
    if (!task) {
      throw new Error(`Task ${taskId} not found`)
    }
    
    // 更新最近执行记录的时间
    const executions = (task as any).executions || []
    if (executions.length > 0) {
      const latestExec = executions[executions.length - 1]
      latestExec.startedAt = timestamp
    }
    
    this.tasks.set(taskId, task)
  }
  
  async getTask(taskId: string): Promise<TaskRecord | null> {
    return this.tasks.get(taskId) || null
  }
  
  async updateTask(task: TaskRecord): Promise<void> {
    this.tasks.set(task.id, task)
  }
  
  // 测试辅助方法
  seed(task: TaskRecord): void {
    this.tasks.set(task.id, task)
  }
  
  clear(): void {
    this.tasks.clear()
  }
}
