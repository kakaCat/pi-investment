/**
 * Checkpoint 类型定义
 * 
 * 用于实施链中断恢复：保存当前执行进度，
 * 中断后可从断点续跑
 */

/**
 * Checkpoint：实施链的执行断点
 */
export interface Checkpoint {
  /** Run ID（实施链的运行标识） */
  runId: string;
  
  /** 当前步骤索引（从0开始） */
  stepIndex: number;
  
  /** 当前正在执行的子卡ID */
  currentSubtaskId?: string;
  
  /** 最后心跳时间（ms timestamp） */
  heartbeatAt: number;
  
  /** Checkpoint 创建时间（ms timestamp） */
  createdAt: number;
  
  /** 已完成的子卡ID列表 */
  completedSubtasks?: string[];
  
  /** 暂停原因（如果已暂停） */
  pauseReason?: string;
}

/**
 * 创建新的 Checkpoint
 */
export function createCheckpoint(runId: string, stepIndex: number = 0): Checkpoint {
  const now = Date.now();
  return {
    runId,
    stepIndex,
    heartbeatAt: now,
    createdAt: now,
    completedSubtasks: []
  };
}

/**
 * 更新 Checkpoint 的心跳
 */
export function updateCheckpointHeartbeat(cp: Checkpoint): Checkpoint {
  return {
    ...cp,
    heartbeatAt: Date.now()
  };
}

/**
 * 推进 Checkpoint 到下一步
 */
export function advanceCheckpoint(
  cp: Checkpoint, 
  completedSubtaskId: string,
  nextSubtaskId?: string
): Checkpoint {
  return {
    ...cp,
    stepIndex: cp.stepIndex + 1,
    currentSubtaskId: nextSubtaskId,
    completedSubtasks: [...(cp.completedSubtasks || []), completedSubtaskId],
    heartbeatAt: Date.now()
  };
}

/**
 * 标记 Checkpoint 为暂停
 */
export function pauseCheckpoint(cp: Checkpoint, reason: string): Checkpoint {
  return {
    ...cp,
    pauseReason: reason,
    heartbeatAt: Date.now()
  };
}

/**
 * 判断 Checkpoint 是否超时（无心跳）
 * @param cp Checkpoint
 * @param thresholdMs 超时阈值（毫秒）
 */
export function isCheckpointStale(cp: Checkpoint, thresholdMs: number): boolean {
  const now = Date.now();
  return now - cp.heartbeatAt > thresholdMs;
}
