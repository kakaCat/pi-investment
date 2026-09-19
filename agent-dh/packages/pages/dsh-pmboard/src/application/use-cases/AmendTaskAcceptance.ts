/**
 * 任务卡验收标准修订（REQ-d3e61a T-9 前置通道）。
 *
 * 为什么需要：任务 acceptance 落库后原本**没有修订通道**（decompose 有幂等守卫，不能重拆），
 * 于是"验收项不可照着验"只能被硬拦却无法修复——那是死锁，不是闸门。本用例提供**唯一**的
 * 修订入口：开工时读到卡、发现验收标准不可执行，先改卡再干活。
 *
 * 载体：挂在既有 reqboard_task_move 的薄壳上（可选参数 acceptance），而不是新开工具——
 * 工具注册表与被改的 use-case 文件当时正被另一窗口占用，新工具需改 src/index.ts（占用面）。
 *
 * 分层：本用例只做"取数 + 落库 + 同步卡文档"；"什么算可证伪"的判定在 domain
 * （domain/task/Acceptability.ts），不在这里重复。
 *
 * @module dsh-pmboard/application/use-cases/AmendTaskAcceptance
 */
import type { UseCaseDeps } from '../ports.js'
import { reject, agentIdFromExec, requireLiveDriver } from '../internal/support.js'
import { openRequirementsFor } from '../internal/window.js'
import { normalizeText } from '../../shared/protocol.js'
import { checkAcceptance } from '../../domain/task/Acceptability.js'
import { fmt } from '../../domain/text/fmt.js'

/** 从 args 里读可选的 acceptance（未传 / 空串 → undefined，表示"不改"）。 */
export function requestedAcceptance(args: unknown): string | undefined {
  const o = (args ?? {}) as Record<string, unknown>
  const v = normalizeText(o.acceptance, 'acceptance', 2000)
  return v.length === 0 ? undefined : v
}

/**
 * 若调用方传了 acceptance → 修订该任务的验收标准（含卡文档同步），返回修订后的文本。
 * 未传 → 返回 undefined（**零行为变更**，不影响既有 task_move 调用）。
 */
export async function amendTaskAcceptanceIfRequested(
  deps: UseCaseDeps,
  args: unknown,
  exec: unknown,
): Promise<string | undefined> {
  const next = requestedAcceptance(args)
  if (next === undefined) return undefined

  const windowKey = agentIdFromExec(deps, exec)
  requireLiveDriver(deps, exec)
  const taskId = normalizeText((args as Record<string, unknown>).task_id, 'task_id', 64)
  if (taskId.length === 0) reject('reqboard_task_move 未执行：修订验收标准需要 task_id', 'REQBOARD_INVALID_INPUT')

  // 修订后的标准至少要过**计划期门槛**（空话/无锚点一律拒），否则等于把弱标准换成更弱的标准
  const verdict = checkAcceptance(taskId, next)
  if (!verdict.ok) reject(fmt('reqboard_task_move 未执行（修订验收标准被拒）：{reason}', { reason: verdict.reason }), 'REQBOARD_INVALID_INPUT')

  const snapshot = deps.repo.snapshot()
  const bound = openRequirementsFor(snapshot, windowKey)
  const task = snapshot.tasks.find(t => t.id === taskId)
  if (task === undefined) reject(fmt('reqboard_task_move 未执行：任务 {id} 不存在', { id: taskId }), 'REQBOARD_TASK_NOT_FOUND')
  if (!bound.some(r => r.id === task.requirementId)) {
    reject(fmt('reqboard_task_move 未执行：任务 {id} 不属于本窗口绑定的需求', { id: taskId }), 'REQBOARD_NOT_BOUND_TO_WINDOW')
  }

  const nowTs = deps.clock.now()
  const result = await deps.repo.mutate('task-amended', (ledger) => {
    const t = ledger.tasks.find(x => x.id === taskId)
    if (t === undefined) return undefined
    t.acceptance = next
    t.updatedAt = nowTs
    return { tasks: [t] }
  })
  if (result.changed.tasks === undefined || result.changed.tasks.length === 0) {
    reject('reqboard_task_move 写入失败：修订验收标准后台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
  }

  // 卡文档同步（人读的唯一事实源）：把「## 得到什么结果」段替换为新文本；无该段则不硬造。
  // 旧卡（改名前的 ## 验收标准）必须继续命中——存量卡不重写，能改才谈得上兼容（REQ-640a55 FR-5）。
  const docPath = 'docs/requirements/' + task.requirementId + '/tasks/' + taskId + '.md'
  try {
    if (deps.docs.exists(docPath)) {
      const text = await deps.docs.read(docPath)
      const lines = text.split(/\r?\n/)
      const start = lines.findIndex(l => /^##\s*(?:得到什么结果|验收标准)/.test(l))
      if (start >= 0) {
        let end = lines.length
        for (let i = start + 1; i < lines.length; i++) {
          if (/^##\s/.test(lines[i])) { end = i; break }
        }
        const rebuilt = [
          ...lines.slice(0, start + 1),
          '',
          next,
          '',
          ...lines.slice(end),
        ].join('\n')
        await deps.docs.write(docPath, rebuilt)
      }
    }
  } catch {
    // 文档同步是**尽力而为**：台账已改成功，卡文档写失败不应把修订整体判失败
  }

  return next
}
