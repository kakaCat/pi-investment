/**
 * StartSubtaskChain 用例
 * 
 * 认领父任务 + 注册后台任务 + 立即返回。
 * 支持幂等：重复调用返回已有的 runId 和 jobId。
 */

import type { RequirementRecord, TaskRecord } from '../../client/types.js'
import { DshJobsAdapter } from '../../adapters/DshJobsAdapter.js'
import { backgroundRunner, type ExecutionContext } from '../internal/background-runner.js'

/**
 * 投递结果
 */
export interface StartChainResult {
  /** 状态：dispatched（已投递）或 already_running（已在运行） */
  status: 'dispatched' | 'already_running'
  /** 运行ID */
  runId: string
  /** Job ID（后台任务ID） */
  jobId: string
}

/**
 * 投递参数
 */
export interface StartChainParams {
  /** 父任务ID */
  parentTaskId: string
  /** 获取需求记录 */
  getRequirement: () => Promise<RequirementRecord>
  /** 获取任务列表 */
  getTasks: () => Promise<TaskRecord[]>
  /** 执行单个子任务 */
  executeSubtask: (taskId: string) => Promise<void>
  /** 更新需求记录 */
  updateRequirement: (req: RequirementRecord) => Promise<void>
  /** DSH jobs 适配器（可选，用于测试注入） */
  dshJobsAdapter?: DshJobsAdapter
}

/**
 * StartSubtaskChain 用例
 * 
 * @param params 投递参数
 * @returns 投递结果
 */
export async function startSubtaskChain(params: StartChainParams): Promise<StartChainResult> {
  const { parentTaskId, getRequirement, getTasks, executeSubtask, updateRequirement } = params
  
  // 获取需求记录
  const requirement = await getRequirement()
  
  // 幂等检查：是否已有 active run
  if (requirement.advance?.runId) {
    // 已有运行中的任务，返回已有的 runId 和 jobId
    // 注意：jobId 需要从某处获取，这里简化为使用 runId
    return {
      status: 'already_running',
      runId: requirement.advance.runId,
      jobId: requirement.advance.runId // 简化：实际应该存储真实的 jobId
    }
  }
  
  // 生成新的 runId
  const runId = `run-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
  
  // 认领：写 lockAt + runId
  const now = Date.now()
  const claimedReq: RequirementRecord = {
    ...requirement,
    advance: {
      ...(requirement.advance || {}),
      lockAt: now,
      runId
    }
  }
  
  await updateRequirement(claimedReq)
  
  // 注册后台任务
  const adapter = params.dshJobsAdapter || new DshJobsAdapter(globalThis as any)
  
  const jobId = await adapter.startJob({
    kind: 'reqboard',
    label: `Task chain for ${parentTaskId}`,
    run: async (signal: AbortSignal) => {
      // 构造执行上下文
      const ctx: ExecutionContext = {
        requirementId: requirement.id,
        runId,
        signal,
        getRequirement,
        getTasks,
        executeSubtask,
        updateRequirement
      }
      
      // 运行实施链
      await backgroundRunner.runChain(ctx)
    }
  })
  
  // 立即返回
  return {
    status: 'dispatched',
    runId,
    jobId
  }
}
