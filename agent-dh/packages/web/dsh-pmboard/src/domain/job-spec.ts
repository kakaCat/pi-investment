/**
 * Job 规格定义
 * 
 * 封装 DSH ctx.jobs 的后台任务规格，
 * 用于实施链的后台执行与状态查询
 */

/**
 * Job 状态
 */
export type JobStatus = 
  | 'pending'    // 已注册，未开始
  | 'running'    // 执行中
  | 'completed'  // 已完成
  | 'failed'     // 失败
  | 'killed';    // 被终止

/**
 * Job 规格
 */
export interface JobSpec {
  /** Job ID（由 ctx.jobs.start 返回） */
  jobId: string;
  
  /** Run ID（实施链的运行标识） */
  runId: string;
  
  /** 当前状态 */
  status: JobStatus;
  
  /** 最后心跳时间（ms timestamp） */
  lastHeartbeat?: number;
  
  /** 启动时间（ms timestamp） */
  startedAt?: number;
  
  /** 完成/失败时间（ms timestamp） */
  finishedAt?: number;
  
  /** 失败原因 */
  error?: string;
}

/**
 * 创建新的 Job 规格
 */
export function createJobSpec(jobId: string, runId: string): JobSpec {
  return {
    jobId,
    runId,
    status: 'pending',
    startedAt: Date.now()
  };
}

/**
 * 更新心跳
 */
export function updateHeartbeat(spec: JobSpec): JobSpec {
  return {
    ...spec,
    lastHeartbeat: Date.now()
  };
}

/**
 * 判断 Job 是否活跃（正在运行）
 */
export function isJobActive(spec: JobSpec): boolean {
  return spec.status === 'running' || spec.status === 'pending';
}

/**
 * 判断 Job 是否终止（完成/失败/被杀）
 */
export function isJobTerminated(spec: JobSpec): boolean {
  return spec.status === 'completed' || spec.status === 'failed' || spec.status === 'killed';
}
