/**
 * QueryRunStatus 用例
 * 
 * 查询实施链运行状态：读取 checkpoint + job 状态，返回快照投影。
 */

import type { RequirementRecord, TaskRecord } from '../../client/types.js'
import type { Checkpoint } from '../../domain/checkpoint.js'
import { CheckpointManager } from '../internal/checkpoint-manager.js'
import { DshJobsAdapter } from '../../adapters/DshJobsAdapter.js'

/**
 * 运行状态
 */
export interface RunStatus {
  /** 运行ID，没有则为 null */
  runId: string | null
  /** 当前步骤索引 */
  stepIndex: number
  /** 当前子任务ID */
  currentSubtaskId?: string
  /** 下一批 ready 的任务ID列表 */
  nextReady: string[]
  /** Job 状态 */
  jobStatus: 'running' | 'completed' | 'failed' | 'not_found'
  /** 暂停原因（如果已暂停） */
  pauseReason?: string
  /** 是否自动运行 */
  autoRun: boolean
}

/**
 * 查询参数
 */
export interface QueryParams {
  /** 需求ID */
  requirementId: string
  /** 获取需求记录 */
  getRequirement: () => Promise<RequirementRecord>
  /** 获取任务列表 */
  getTasks: () => Promise<TaskRecord[]>
  /** DSH jobs 适配器（可选，用于测试注入） */
  dshJobsAdapter?: DshJobsAdapter
}

/**
 * QueryRunStatus 用例
 * 
 * @param params 查询参数
 * @returns 运行状态快照
 */
export async function queryRunStatus(params: QueryParams): Promise<RunStatus> {
  const { requirementId, getRequirement, getTasks } = params
  const checkpointManager = new CheckpointManager()
  
  // 获取需求记录
  const requirement = await getRequirement()
  
  // 读取 checkpoint
  const checkpoint = checkpointManager.readCheckpoint(requirement)
  
  if (!checkpoint || !checkpoint.runId) {
    // 没有运行中的任务
    const tasks = await getTasks()
    const nextReady = findReadyTasks(tasks).map(t => t.id)
    
    return {
      runId: null,
      stepIndex: 0,
      nextReady,
      jobStatus: 'not_found',
      autoRun: false
    }
  }
  
  // 有 checkpoint，查询 job 状态
  const adapter = params.dshJobsAdapter || new DshJobsAdapter(globalThis as any)
  
  let jobStatus: 'running' | 'completed' | 'failed' | 'not_found' = 'not_found'
  
  try {
    const jobSnapshot = await adapter.getJob(checkpoint.runId)
    
    if (jobSnapshot) {
      switch (jobSnapshot.status) {
        case 'running':
          jobStatus = 'running'
          break
        case 'completed':
          jobStatus = 'completed'
          break
        case 'failed':
          jobStatus = 'failed'
          break
        default:
          jobStatus = 'not_found'
      }
    }
  } catch (error) {
    // Job 不存在或查询失败
    jobStatus = 'not_found'
  }
  
  // 获取下一批 ready 任务
  const tasks = await getTasks()
  const nextReady = findReadyTasks(tasks).map(t => t.id)
  
  // 判断暂停原因
  let pauseReason: string | undefined
  if (jobStatus === 'completed' && nextReady.length === 0) {
    const allDone = tasks.every(t => t.status === 'done')
    if (!allDone) {
      pauseReason = '有任务但都不 ready（可能在等待依赖）'
    }
  }
  
  return {
    runId: checkpoint.runId,
    stepIndex: checkpoint.stepIndex || 0,
    currentSubtaskId: checkpoint.currentSubtaskId,
    nextReady,
    jobStatus,
    pauseReason,
    autoRun: jobStatus === 'running'
  }
}

/**
 * 查找 ready 状态的任务
 * 
 * @param tasks 任务列表
 * @returns ready 任务列表
 */
function findReadyTasks(tasks: TaskRecord[]): TaskRecord[] {
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
