/**
 * DSH Jobs 适配器
 * 
 * 封装 ctx.jobs.start/get 为领域友好接口，
 * 用于实施链的后台执行与状态查询
 */

import type { JobStatus } from '../domain/job-spec.js'
// JobsPort 的形状来自 application（除类型外零依赖）——REQ-260927144541-0481 根因修复：
// 本类此前只有 startJob/getJob，装配层拿不到 `deps.jobs` 要求的 start/get/available，
// 于是 JobsPort 从未装配、实施链恒走同步兼容路径。
import type { JobsPort, JobStartSpec, JobSnapshot as PortJobSnapshot } from '../application/ports.js'

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
export class DshJobsAdapter implements JobsPort {
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
        run: this.toProducerHooks(params.run),
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
   * JobsPort.start（REQ-260927144541-0481 根因修复）：交给 ctx.jobs，含 owner——保住
   * DSH 的 owner 隔离与并发上限（旧 startJob 丢掉了 owner）。run 经 toProducerHooks
   * 翻译成 DSH 的生产者钩子（见下方契约说明）。同步返回 Job ID，不等执行完成：
   * 调用方（reqboard_task_run）因此立即拿到回执。
   */
  async start(spec: JobStartSpec): Promise<string> {
    return this.ctx.jobs.start({
      kind: spec.kind,
      label: spec.label,
      owner: spec.owner,
      run: this.toProducerHooks(spec.run),
    })
  }

  /**
   * 把应用层的「执行函数」翻译成 DSH 的生产者钩子（JobHooks）。
   *
   * DSH 契约（@deepseek-ai/dsh-jobs JobStart.run）要求 run() **同步返回**
   * `{ cancel, done, readOutput? }`；注册表随后调 `hooks.cancel.bind(hooks)`
   * （dsh-jobs-local/lib/index.js:152）。2026-09-27 线上实测：直接把 async 执行函数
   * 当 run 传过去 → run() 返回 Promise → `hooks.cancel` 为 undefined →
   * `undefined.bind(hooks)` 抛 TypeError → 投递恒失败（REQBOARD_DISPATCH_FAILED）。
   * 翻译只属于适配层：应用层 JobStartSpec 的 (signal) => Promise<void> 形状保持不变。
   */
  private toProducerHooks(run: (signal: AbortSignal) => Promise<void>) {
    return () => {
      const controller = new AbortController()
      // done 必须 resolve（不得 reject），失败以 { status:'failed' } 结算。
      const done = (async (): Promise<{ status: 'completed' | 'failed'; detail?: string }> => {
        try {
          await run(controller.signal)
          return { status: 'completed' }
        } catch (error) {
          return { status: 'failed', detail: error instanceof Error ? error.message : String(error) }
        }
      })()
      return {
        // cancel 必须同步、幂等（AbortController.abort 天然满足）。
        cancel: (reason?: string): void => { controller.abort(reason) },
        done,
      }
    }
  }

  /** JobsPort.get：复用已做状态映射的 getJob（同一份口径，避免两处映射漂移）。 */
  async get(jobId: string): Promise<PortJobSnapshot | null> {
    return this.getJob(jobId)
  }

  /** JobsPort.available：能构造出实例即证明 ctx.jobs.start/get 俱在（构造器已校验）。 */
  available(): boolean {
    return true
  }

  /**
   * 检查 ctx.jobs 是否可用（静态方法）
   */
  static isAvailable(ctx: any): boolean {
    // 空值安全：宿主 inject 回调可能拿到 undefined ctx（测试假宿主实测）——探测函数不得自己抛错。
    return !!(ctx?.jobs && typeof ctx.jobs.start === 'function' && typeof ctx.jobs.get === 'function')
  }
}
