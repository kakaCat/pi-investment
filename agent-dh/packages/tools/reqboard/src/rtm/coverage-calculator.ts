/**
 * 三层覆盖度统计（REQ-260926140539-457b FR-5）。
 *
 * 设计覆盖度 = 有设计章节的 FR / 全部 FR（门禁 100%）；
 * 实施覆盖度 = 有任务实现的设计章节 / 全部设计章节（门禁 100%）；
 * 测试覆盖度 = 有测试用例的任务 / 全部任务（门禁 ≥80%）。
 * 空集合按"无待覆盖项"计 100%（vacuous truth），uncovered 恒为 []。
 *
 * @module @pi-investment/reqboard/rtm/coverage-calculator
 */
import type {
  Coverage,
  DesignCoverage,
  DesignSection,
  FR,
  ImplementationCoverage,
  RTMTaskLike,
  TestingCoverage,
} from './types.js'

/** 百分比四舍五入；分母为 0 时按 100 计。 */
export function rateOf(covered: number, total: number): number {
  if (total <= 0) return 100
  return Math.round((covered / total) * 100)
}

/** 设计覆盖度（FR 视角）。 */
export function calculateDesignCoverage(
  frs: readonly FR[],
  frToDesign: Record<string, string[]>,
): DesignCoverage {
  const uncovered: string[] = []
  let covered = 0
  for (const fr of frs) {
    const refs = frToDesign[fr.id] ?? []
    if (refs.length > 0) covered += 1
    else uncovered.push(fr.id)
  }
  return {
    total: frs.length,
    covered,
    uncovered,
    rate: rateOf(covered, frs.length),
    total_frs: frs.length,
    covered_frs: covered,
  }
}

/** 实施覆盖度（设计章节视角）。 */
export function calculateImplementationCoverage(
  sections: readonly DesignSection[],
  designToTasks: Record<string, string[]>,
): ImplementationCoverage {
  const uncovered: string[] = []
  let covered = 0
  for (const s of sections) {
    const tasks = designToTasks[s.ref] ?? []
    if (tasks.length > 0) covered += 1
    else uncovered.push(s.ref)
  }
  return {
    total: sections.length,
    covered,
    uncovered,
    rate: rateOf(covered, sections.length),
    total_designs: sections.length,
    covered_designs: covered,
  }
}

/** 测试覆盖度（任务视角）。 */
export function calculateTestingCoverage(
  tasks: readonly RTMTaskLike[],
  taskToTests: Record<string, string[]>,
): TestingCoverage {
  const uncovered: string[] = []
  let covered = 0
  for (const t of tasks) {
    const tests = taskToTests[t.id] ?? []
    if (tests.length > 0) covered += 1
    else uncovered.push(t.id)
  }
  return {
    total: tasks.length,
    covered,
    uncovered,
    rate: rateOf(covered, tasks.length),
    total_tasks: tasks.length,
    tested_tasks: covered,
    untested: [...uncovered],
  }
}

/** 直接从一个 Coverage 生成门禁可读的一句话。 */
export function describeCoverage(label: string, c: Coverage): string {
  return `${label}覆盖度 ${c.rate}%（${c.covered}/${c.total}）`
}
