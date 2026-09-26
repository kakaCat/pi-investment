/**
 * 四级追溯映射构建（REQ-260926140539-457b FR-4）。
 *
 * 链路：FR → 设计章节 → 任务 → 测试用例。
 * 构建规则（可证伪）：
 *  - fr_to_design：章节的 serves 包含该 FR；
 *  - design_to_tasks：任务的 serves 与章节的 serves 有交集，或任务显式 implements 该章节；
 *  - task_to_tests：测试用例的 covers 包含该任务；
 *  - fr_to_tasks / fr_to_tests：由上游映射推导（间接映射）。
 *
 * @module @pi-investment/reqboard/rtm/traceability-builder
 */
import type { DesignSection, FR, RTMTaskLike, TestCase, Traceability } from './types.js'
import { taskServes } from './parser.js'

/** FR → 设计章节。 */
export function buildFRToDesign(
  frs: readonly FR[],
  sections: readonly DesignSection[],
): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const fr of frs) out[fr.id] = []
  for (const s of sections) {
    for (const frId of s.serves) {
      const list = out[frId] ?? (out[frId] = [])
      if (!list.includes(s.ref)) list.push(s.ref)
    }
  }
  return out
}

/** 设计章节 → 任务。 */
export function buildDesignToTasks(
  sections: readonly DesignSection[],
  tasks: readonly RTMTaskLike[],
): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const s of sections) {
    const hits: string[] = []
    for (const t of tasks) {
      const direct = t.implements === s.ref
      const overlap = taskServes(t).some(fr => s.serves.includes(fr))
      if (direct || overlap) hits.push(t.id)
    }
    out[s.ref] = hits
  }
  return out
}

/** 任务 → 测试用例。 */
export function buildTaskToTests(
  tasks: readonly RTMTaskLike[],
  testCases: readonly TestCase[],
): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const t of tasks) out[t.id] = []
  for (const tc of testCases) {
    for (const taskId of tc.covers) {
      const list = out[taskId] ?? (out[taskId] = [])
      if (!list.includes(tc.id)) list.push(tc.id)
    }
  }
  return out
}

/** FR → 任务（由 fr_to_design 与 design_to_tasks 推导）。 */
export function buildFRToTasks(
  frToDesign: Record<string, string[]>,
  designToTasks: Record<string, string[]>,
  frIds?: readonly string[],
): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const fr of frIds ?? Object.keys(frToDesign)) out[fr] = []
  for (const [fr, refs] of Object.entries(frToDesign)) {
    const list = out[fr] ?? (out[fr] = [])
    for (const ref of refs) {
      for (const taskId of designToTasks[ref] ?? []) {
        if (!list.includes(taskId)) list.push(taskId)
      }
    }
  }
  return out
}

/** FR → 测试用例（由 fr_to_tasks 与 task_to_tests 推导）。 */
export function buildFRToTests(
  frToTasks: Record<string, string[]>,
  taskToTests: Record<string, string[]>,
  frIds?: readonly string[],
): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const fr of frIds ?? Object.keys(frToTasks)) out[fr] = []
  for (const [fr, tasks] of Object.entries(frToTasks)) {
    const list = out[fr] ?? (out[fr] = [])
    for (const taskId of tasks) {
      for (const tc of taskToTests[taskId] ?? []) {
        if (!list.includes(tc)) list.push(tc)
      }
    }
  }
  return out
}

/** 组装完整追溯块。 */
export function buildTraceability(input: {
  frs: readonly FR[]
  sections: readonly DesignSection[]
  tasks: readonly RTMTaskLike[]
  testCases: readonly TestCase[]
}): Required<Traceability> {
  const frIds = input.frs.map(f => f.id)
  const fr_to_design = buildFRToDesign(input.frs, input.sections)
  const design_to_tasks = buildDesignToTasks(input.sections, input.tasks)
  const task_to_tests = buildTaskToTests(input.tasks, input.testCases)
  const fr_to_tasks = buildFRToTasks(fr_to_design, design_to_tasks, frIds)
  const fr_to_tests = buildFRToTests(fr_to_tasks, task_to_tests, frIds)
  return { fr_to_design, design_to_tasks, fr_to_tasks, task_to_tests, fr_to_tests }
}

/** 一条 FR 的完整追溯链（FR-7 会话节点展示用）。 */
export interface TraceabilityChain {
  fr: string
  designs: string[]
  tasks: string[]
  tests: string[]
}

/** 取单条 FR 的追溯链。 */
export function buildTraceabilityChain(frId: string, trace: Traceability): TraceabilityChain {
  return {
    fr: frId,
    designs: [...(trace.fr_to_design?.[frId] ?? [])],
    tasks: [...(trace.fr_to_tasks?.[frId] ?? [])],
    tests: [...(trace.fr_to_tests?.[frId] ?? [])],
  }
}
