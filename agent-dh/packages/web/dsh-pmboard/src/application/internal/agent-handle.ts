/**
 * 子卡派发的 **agent 句柄**解析（D14 / REQ-260927123256-196b）。
 *
 * 为什么要它：子卡 workflow 由引擎启动时读 `request.parent.session`，而 `parent` 取自
 * `exec.agent`。工具路径（`reqboard_task_run`）自带 exec.agent；**看板「继续」与启动恢复**
 * 这两条入口没有调用窗口的 exec → `parent` undefined → 引擎抛
 * `Cannot read properties of undefined (reading 'session')`（实测 04:49:17，链被判定 start_failed）。
 *
 * 这里按父卡所属需求的**绑定窗口**（sourceSessionId）兜底查在线 agent；解不到则返回可读原因，
 * 由调用方判失败——不把引擎的 TypeError 当结论。**未装配 `deps.agents` 端口时保持既有行为**
 * （原样透传，由引擎决定），以免破坏内存测试 / 嵌入调用方的契约。
 *
 * @module dsh-pmboard/application/internal/agent-handle
 */
import type { UseCaseDeps } from '../ports.js'
import type { TaskRecord } from '../../shared/protocol.js'
import { fmt } from '../../domain/text/fmt.js'

export type AgentHandleResult = { ok: true; exec: unknown } | { ok: false; reason: string }

/**
 * 解析一张子卡可用的 agent 句柄。优先调用方传入的 `exec.agent`；缺省按父卡所属需求的绑定窗口
 * 查在线 agent（`deps.agents()`）。三条入口（工具/看板/启动恢复）由此统一。
 */
export function ensureAgentHandle(
  deps: UseCaseDeps,
  parentId: string,
  subtaskId: string,
  exec: unknown,
  tasks: readonly TaskRecord[],
): AgentHandleResult {
  const existing = (exec as { agent?: unknown } | undefined)?.agent
  if (existing !== undefined) return { ok: true, exec }
  if (deps.agents === undefined) return { ok: true, exec }
  const snap = deps.repo.snapshot()
  // 队列任务（REQ-260927202051-f6df D4：`LedgerView.tasks` 随 v9 移除）
  const parent = tasks.find((t) => t.id === parentId)
  const req = parent === undefined ? undefined : snap.requirements.find((r) => r.id === parent.requirementId)
  const windowKey = req?.sourceSessionId
  const agent = typeof windowKey === 'string' && windowKey.length > 0 ? deps.agents?.()?.get?.(windowKey) : undefined
  if (agent !== undefined) return { ok: true, exec: { agent } }
  return {
    ok: false,
    reason: fmt(
      '子卡 {sub} 派发缺少 agent 句柄：绑定窗口 {wk} 不在线——请由该窗口调 reqboard_task_run 续跑（看板「继续」/启动恢复仅在窗口在线时可派发）',
      { sub: subtaskId, wk: windowKey ?? '(未知)' },
    ),
  }
}
