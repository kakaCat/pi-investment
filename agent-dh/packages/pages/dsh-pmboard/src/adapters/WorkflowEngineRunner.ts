/**
 * WorkflowRunner 端口的**唯一实现**（REQ-4842fe t4 / FR-4）：直接消费已加载的
 * `ctx.workflowEngine`，不经过被禁用的 `tool-workflow` 模型侧工具。
 *
 * 契约要点（design/workflow-engine-contract §3）：
 *  - `start()` 同步抛错 = 请求无法开始（meta 非法 / 脚本解析失败）→ 翻译为 ok:false；
 *  - `run.result` **永不 reject**：失败以 stopReason(error/cancelled) 表达；
 *  - 调用方必须 `dispose()`（幂等）；此处 finally 兜底，保证子卡链走完后 worker 不悬挂。
 *
 * @module dsh-pmboard/adapters/WorkflowEngineRunner
 */
import type { WorkflowRunOutcome, WorkflowRunner, WorkflowStartInput } from '../application/ports.js'

/** 引擎的最小结构（不 import @deepseek-ai/dsh-workflow，保持 adapter 只桥接形状）。 */
export interface WorkflowRunLike {
  result: Promise<{ value?: unknown; stopReason?: string; error?: string }>
  cancel?: (reason?: string) => void
  dispose?: () => Promise<void>
}

export interface WorkflowEngineLike {
  start(request: {
    script: string
    meta: { name: string; description: string; phases?: string[] }
    args?: unknown
    parent: unknown
    signal?: unknown
  }): WorkflowRunLike
}

function describe(err: unknown): string {
  if (err instanceof Error) return err.message
  return String(err)
}

/**
 * `engine` 以 thunk 形式注入：服务工作区尚未就绪时返回 undefined，
 * 此时 start() **显式失败**（reason=engine_unavailable）——不静默成功。
 */
export class WorkflowEngineRunner implements WorkflowRunner {
  constructor(private readonly engine: () => WorkflowEngineLike | undefined) {}

  async start(input: WorkflowStartInput): Promise<WorkflowRunOutcome> {
    const engine = this.engine()
    if (engine === undefined) return { ok: false, reason: 'engine_unavailable' }
    let run: WorkflowRunLike
    try {
      run = engine.start({
        script: input.script,
        meta: input.meta,
        args: input.args,
        parent: input.parent,
        signal: input.signal,
      })
    } catch (err) {
      // 同步抛错 = 请求无法开始（META_INVALID / SCRIPT_PARSE 等）。
      return { ok: false, reason: 'start_failed: ' + describe(err) }
    }
    try {
      const settled = await run.result
      if (settled === undefined || settled.stopReason !== 'completed') {
        return { ok: false, reason: (settled?.stopReason ?? 'error') + (settled?.error !== undefined ? ': ' + settled.error : '') }
      }
      return { ok: true, value: settled.value }
    } catch (err) {
      // 契约规定 result 不 reject；防御性兜底，宁可判失败也不静默成功。
      return { ok: false, reason: 'result_rejected: ' + describe(err) }
    } finally {
      if (typeof run.dispose === 'function') {
        try {
          await run.dispose()
        } catch {
          // dispose 失败不改变已定结果（worker 回收是尽力而为）。
        }
      }
    }
  }
}
