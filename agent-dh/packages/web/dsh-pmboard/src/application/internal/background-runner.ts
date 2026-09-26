/**
 * 后台执行器
 * 
 * 实现实施链的后台循环：选择子卡→执行→写checkpoint→心跳→下一步。
 * 支持取消信号和中断续传。
 */

import type { RequirementRecord, TaskRecord } from '../../client/types.js'
import type { Checkpoint } from '../../domain/checkpoint.js'
import { scheduleBatches } from './batch-scheduler.js'
import { CheckpointManager } from './checkpoint-manager.js'
import { LIMITS } from '../../domain/limits.js'

/**
 * 执行上下文
 */
export interface ExecutionContext {
  /** 需求ID */
  requirementId: string
  /** 运行ID */
  runId: string
  /** 取消信号 */
  signal: AbortSignal
  /** 获取需求记录 */
  getRequirement: () => Promise<RequirementRecord>
  /** 获取任务列表 */
  getTasks: () => Promise<TaskRecord[]>
  /** 执行单个子任务 */
  executeSubtask: (taskId: string) => Promise<void>
  /** 更新需求记录 */
  updateRequirement: (req: RequirementRecord) => Promise<void>
}

/**
 * 执行结果
 */
export interface ExecutionResult {
  /** 完成状态 */
  status: 'completed' | 'paused' | 'cancelled' | 'failed'
  /** 总执行步数 */
  totalSteps: number
  /** 最后的 checkpoint */
  lastCheckpoint?: Checkpoint
  /** 错误信息（如果失败） */
  error?: string
}

/**
 * 后台执行器
 */
export class BackgroundRunner {
  private checkpointManager = new CheckpointManager()
  
  /**
   * 运行实施链
   * 
   * @param ctx 执行上下文
   * @returns 执行结果
   */
  async runChain(ctx: ExecutionContext): Promise<ExecutionResult> {
    let stepIndex = 0
    let lastCheckpoint: Checkpoint | undefined
    
    try {
      // 设置心跳定时器
      const heartbeatInterval = this.setupHeartbeat(ctx)
      
      // 主循环
      while (!ctx.signal.aborted) {
        // 获取当前状态
        const requirement = await ctx.getRequirement()
        const tasks = await ctx.getTasks()
        
        // 过滤出 ready 状态的任务（todo 且依赖已完成）
        const readyTasks = this.findReadyTasks(tasks)
        
        if (readyTasks.length === 0) {
          // 没有可执行任务，检查是否全部完成
          const allDone = tasks.every(t => t.status === 'done')
          
          if (allDone) {
            clearInterval(heartbeatInterval)
            return {
              status: 'completed',
              totalSteps: stepIndex,
              lastCheckpoint
            }
          }
          
          // 有任务但都不 ready（可能在等待），暂停
          clearInterval(heartbeatInterval)
          return {
            status: 'paused',
            totalSteps: stepIndex,
            lastCheckpoint
          }
        }
        
        // 批调度：按写集分批
        const { batches } = scheduleBatches(readyTasks)
        
        // 逐批执行（批间串行）
        for (const batch of batches) {
          if (ctx.signal.aborted) break
          
          // 批内并行执行
          await Promise.all(
            batch.taskIds.map(taskId => ctx.executeSubtask(taskId))
          )
          
          stepIndex++
          
          // 写 checkpoint
          const checkpoint: Checkpoint = {
            runId: ctx.runId,
            currentSubtaskId: batch.taskIds[0], // 记录第一个任务ID
            stepIndex,
            heartbeatAt: Date.now()
          }
          
          lastCheckpoint = checkpoint
          
          const updatedReq = this.checkpointManager.writeCheckpoint(requirement, checkpoint)
          await ctx.updateRequirement(updatedReq)
        }
      }
      
      // 被取消
      clearInterval(heartbeatInterval)
      return {
        status: 'cancelled',
        totalSteps: stepIndex,
        lastCheckpoint
      }
      
    } catch (error) {
      return {
        status: 'failed',
        totalSteps: stepIndex,
        lastCheckpoint,
        error: error instanceof Error ? error.message : String(error)
      }
    }
  }
  
  /**
   * 查找 ready 状态的任务
   * 
   * @param tasks 任务列表
   * @returns ready 任务列表
   */
  private findReadyTasks(tasks: TaskRecord[]): TaskRecord[] {
    return tasks.filter(task => {
      // 只处理 todo 状态
      if (task.status !== 'todo') {
        return false
      }
      
      // 检查依赖是否全部完成
      const deps = task.dependsOn || []
      const allDepsDone = deps.every(depId => {
        const depTask = tasks.find(t => t.id === depId)
        return depTask?.status === 'done'
      })
      
      return allDepsDone
    })
  }
  
  /**
   * 设置心跳定时器
   * 
   * @param ctx 执行上下文
   * @returns 定时器ID
   */
  private setupHeartbeat(ctx: ExecutionContext): NodeJS.Timeout {
    return setInterval(async () => {
      try {
        const requirement = await ctx.getRequirement()
        const updated = this.checkpointManager.updateHeartbeat(requirement)
        await ctx.updateRequirement(updated)
      } catch (error) {
        console.error('[background-runner] Heartbeat update failed:', error)
      }
    }, LIMITS.heartbeatIntervalMs)
  }
}

/**
 * 默认的后台执行器实例
 */
export const backgroundRunner = new BackgroundRunner()
