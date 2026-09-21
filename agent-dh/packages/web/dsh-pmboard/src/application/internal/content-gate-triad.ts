/**
 * 三要素门禁接线（REQ-640a55 t-fb5e66 / FR-1）——把 content-gates.checkTaskCardTriad 接上执行链。
 *
 * 为什么单独成文件而不是塞进 content-gate-wiring.ts：那个文件已有 369 行，本仓尺寸门禁
 * （size-budget.test.ts）单文件 ≤400 行。本模块与它同层同职责（**取数与组装**），判定仍零 IO：
 *   content-gates.ts       给定 ParsedDoc → 缺口（纯函数，无 IO）
 *   content-gate-triad.ts  **本文件**：读卡文件、解析、拼缺口文案
 *
 * 门禁挂在哪两个时刻（见 design/architecture.md）：
 *   ① decomposing → implementing 出口（需求级，一次扫全部卡）：卡读不懂就不许开工；
 *   ② task_move(to=done)（单卡）：防卡在拆分后被改坏或覆盖。
 *
 * @module dsh-pmboard/application/internal/content-gate-triad
 */
import { checkTaskCardTriad, parseDocument, type DocsReader } from './content-gates.js'

/** 一张卡的三要素缺口（missing = 硬拦项；warnings = 建议级，不阻断）。 */
export interface TaskCardTriadGap {
  taskId: string
  missing: string[]
  warnings: string[]
}

/** 门禁所需的最小任务投影（避免把整个 TaskRecord 拖进来）。 */
export interface TriadTaskLike {
  id: string
  requirementId: string
}

/**
 * 逐卡扫描三要素缺口（只读，无副作用）。
 *
 * 刻意不判的两种情形：卡文件尚不存在（那是"卡还没落盘"，别的门禁管落盘）、
 * 缺卡的那节只是 warnings（避免形式主义）。
 */
export async function taskCardTriadGaps(
  docs: DocsReader,
  input: { requirementId: string; taskIds: readonly string[] },
): Promise<TaskCardTriadGap[]> {
  const out: TaskCardTriadGap[] = []
  for (const taskId of input.taskIds) {
    const rel = 'docs/requirements/' + input.requirementId + '/tasks/' + taskId + '.md'
    if (!docs.exists(rel)) continue
    const verdict = checkTaskCardTriad(parseDocument(await docs.read(rel)))
    if (verdict.missing.length > 0) out.push({ taskId, missing: verdict.missing, warnings: verdict.warnings })
  }
  return out
}

/**
 * 需求级门禁（拆分出口）：命中即返回缺口文案（undefined = 放行）。
 * 只在 to === 'implementing' 时生效——其余目标态与"卡写得合不合格"无关。
 */
export async function requirementTaskCardTriadFailure(
  docs: DocsReader,
  input: { requirementId: string; to: string; tasks: readonly TriadTaskLike[] },
): Promise<string | undefined> {
  if (input.to !== 'implementing') return undefined
  const mine = input.tasks.filter(t => t.requirementId === input.requirementId)
  if (mine.length === 0) return undefined
  const gaps = await taskCardTriadGaps(docs, { requirementId: input.requirementId, taskIds: mine.map(t => t.id) })
  if (gaps.length === 0) return undefined
  return gaps.map(g => g.taskId + '（' + g.missing.join('；') + '）').join('、')
}

/**
 * 单卡门禁（结单前）：与 doneEvidenceAnchorFailure 同款——状态与越权判定都留在本层，
 * 工具壳只负责调用与拒绝（架构门禁：tools/ 不许出现状态字面量）。
 * 不判的三种情形：to 不是 done / 任务不在台账 / 任务所属需求不属本窗口绑定集合。
 */
export async function taskCardTriadFailure(
  docs: DocsReader,
  input: {
    taskId: string
    to: string
    tasks: readonly TriadTaskLike[]
    boundRequirementIds: readonly string[]
  },
): Promise<string | undefined> {
  if (input.to !== 'done') return undefined
  const task = input.tasks.find(t => t.id === input.taskId)
  if (task === undefined) return undefined
  if (!input.boundRequirementIds.includes(task.requirementId)) return undefined
  const gaps = await taskCardTriadGaps(docs, { requirementId: task.requirementId, taskIds: [task.id] })
  return gaps.length === 0 ? undefined : gaps[0].missing.join('；')
}
