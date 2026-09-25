/**
 * DSH Jobs 适配器
 * 
 * 封装 ctx.jobs.start/get 为领域友好接口，
 * 用于实施链的后台执行与状态查询
 */

import type { JobSpec, JobStatus } from '../domain/job-spec.js'

/**
 * DSH Jobs 不可用错误
 */
export class DshJobsUnavailable extends Error {
  constructor(message = 'ctx.jobs is not available') {
    super(message)
    this.name = 'DshJobsUnavailable'
  }
}

/**
 * Job 启动参数
 */
export interface JobStartParams {
  /** Job 类型标识 */
  kind: string
  /** Job 执行函数 */
  run: (signal: AbortSignal) => Promise<void>
  /** Job 标签（可选，用于日志） */
  label?: string
}

/**
 * Job 快照（从 ctx.jobs.get 返回）
 */
export interface JobSnapshot {
  id: string
  status: JobStatus
  startedAt?: number
  finishedAt?: number
  error?: string
}

/**
 * DSH Jobs 适配器
 */
export class DshJobsAdapter {
  private ctx: any

  constructor(ctx: any) {
    this.ctx = ctx
    
    // 启动时检测 ctx.jobs 存在性
    if (!ctx.jobs || typeof ctx.jobs.start !== 'function') {
      throw new DshJobsUnavailable('ctx.jobs.start is not available')
    }
    if (typeof ctx.jobs.get !== 'function') {
      throw new DshJobsUnavailable('ctx.jobs.get is not available')
    }
  }

  /**
   * 启动后台任务
   * @returns Job ID
   */
  async startJob(params: JobStartParams): Promise<string> {
    try {
      const jobId = await this.ctx.jobs.start({
        kind: params.kind,
        run: params.run,
        label: params.label
      })
      
      return jobId
    } catch (error) {
      throw new Error(`Failed to start job: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 获取 Job 快照
   * @param jobId Job ID
   * @returns Job 快照，如果 job 不存在则返回 null
   */
  async getJob(jobId: string): Promise<JobSnapshot | null> {
    try {
      const job = await this.ctx.jobs.get(jobId)
      
      if (!job) {
        return null
      }

      // 映射 DSH job 状态到领域 JobStatus
      const status = this.mapJobStatus(job.status)

      return {
        id: jobId,
        status,
        startedAt: job.startedAt,
        finishedAt: job.finishedAt,
        error: job.error
      }
    } catch (error) {
      throw new Error(`Failed to get job ${jobId}: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 映射 DSH job 状态到领域 JobStatus
   */
  private mapJobStatus(dshStatus: string): JobStatus {
    switch (dshStatus) {
      case 'pending':
        return 'pending'
      case 'running':
        return 'running'
      case 'completed':
        return 'completed'
      case 'failed':
        return 'failed'
      case 'killed':
        return 'killed'
      default:
        // 未知状态默认为 running
        return 'running'
    }
  }

  /**
   * 检查 ctx.jobs 是否可用（静态方法）
   */
  static isAvailable(ctx: any): boolean {
    return !!(ctx.jobs && typeof ctx.jobs.start === 'function' && typeof ctx.jobs.get === 'function')
  }
}
