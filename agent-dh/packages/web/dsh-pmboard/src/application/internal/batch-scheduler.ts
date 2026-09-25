/**
 * 批调度器
 * 
 * 按写集分批，批内并发、批间串行。
 * 贪心算法：依次尝试将每个任务加入当前批，不冲突则加入，冲突则开新批。
 */

import type { TaskRecord } from '../../client/types.js'
import { detectConflict, type WriteSet } from '../../domain/write-set.js'

/**
 * 批次：一组可并行执行的子任务
 */
export interface Batch {
  /** 批次序号（从0开始） */
  index: number
  /** 任务ID列表 */
  taskIds: string[]
  /** 合并后的写集（所有任务的写集并集） */
  mergedWriteSet: WriteSet
}

/**
 * 调度结果
 */
export interface ScheduleResult {
  /** 批次列表 */
  batches: Batch[]
  /** 参与调度的任务总数 */
  totalTasks: number
  /** 最大批次大小（批内任务数） */
  maxBatchSize: number
}

/**
 * 批调度器：按写集冲突分批
 * 
 * @param readySubtasks 待调度的子任务列表（已过滤为 ready 状态）
 * @returns 调度结果（批次列表）
 */
export function scheduleBatches(readySubtasks: TaskRecord[]): ScheduleResult {
  const batches: Batch[] = []
  const taskMap = new Map<string, TaskRecord>()
  
  // 构建任务映射
  for (const task of readySubtasks) {
    taskMap.set(task.id, task)
  }
  
  // 拓扑排序：确保依赖任务先调度
  const sorted = topologicalSort(readySubtasks)
  
  // 贪心分批
  for (const task of sorted) {
    const writeSet = task.filesPlanned || []
    let placed = false
    
    // 尝试放入现有批次
    for (const batch of batches) {
      // 检查是否与批次内任何任务冲突
      if (!detectConflict(writeSet, batch.mergedWriteSet)) {
        // 不冲突，加入该批
        batch.taskIds.push(task.id)
        batch.mergedWriteSet.push(...writeSet)
        placed = true
        break
      }
    }
    
    // 无法放入现有批次，开新批
    if (!placed) {
      batches.push({
        index: batches.length,
        taskIds: [task.id],
        mergedWriteSet: [...writeSet]
      })
    }
  }
  
  // 计算统计信息
  const maxBatchSize = batches.reduce((max, batch) => Math.max(max, batch.taskIds.length), 0)
  
  return {
    batches,
    totalTasks: readySubtasks.length,
    maxBatchSize
  }
}

/**
 * 拓扑排序：确保依赖任务先调度
 * 
 * 简化实现：暂时按 dependsOn 为空的优先
 */
function topologicalSort(tasks: TaskRecord[]): TaskRecord[] {
  const taskMap = new Map<string, TaskRecord>()
  const inDegree = new Map<string, number>()
  
  // 初始化
  for (const task of tasks) {
    taskMap.set(task.id, task)
    inDegree.set(task.id, 0)
  }
  
  // 计算入度（我依赖多少任务）
  for (const task of tasks) {
    const deps = task.dependsOn || []
    inDegree.set(task.id, deps.filter(depId => taskMap.has(depId)).length)
  }
  
  // 按入度升序排序（依赖少的先调度）
  return Array.from(tasks).sort((a, b) => {
    const degreeA = inDegree.get(a.id) || 0
    const degreeB = inDegree.get(b.id) || 0
    return degreeA - degreeB
  })
}

/**
 * 验证批次有效性
 * 
 * @param batch 批次
 * @returns true=有效，false=批内有冲突
 */
export function validateBatch(batch: Batch, taskMap: Map<string, TaskRecord>): boolean {
  const tasks = batch.taskIds.map(id => taskMap.get(id)).filter(Boolean) as TaskRecord[]
  
  // 检查批内任意两个任务的写集是否冲突
  for (let i = 0; i < tasks.length; i++) {
    for (let j = i + 1; j < tasks.length; j++) {
      const ws1 = tasks[i].filesPlanned || []
      const ws2 = tasks[j].filesPlanned || []
      
      if (detectConflict(ws1, ws2)) {
        return false
      }
    }
  }
  
  return true
}
