/**
 * rtm-accepting.yml 生成（REQ-260926140539-457b FR-2 触发点 7）。
 *
 * 产出：测试用例、任务 → 测试 / FR → 测试映射、测试覆盖度（门禁 ≥80%）。
 *
 * @module @pi-investment/reqboard/rtm/accepting-generator
 */
import { getRTMPath, readRTM, writeRTM } from './file-io.js'
import type { RTMContext } from './context.js'
import { parseTestCovers } from './parser.js'
import { buildFRToTests, buildTaskToTests } from './traceability-builder.js'
import { calculateTestingCoverage } from './coverage-calculator.js'
import { effectiveFRs } from './design-generator.js'
import type { RTMAccepting, RTMDecomposing } from './types.js'

/** 生成/更新 rtm-accepting.yml。 */
export function generateAcceptingRTM(ctx: RTMContext, reqId: string): RTMAccepting {
  const filePath = getRTMPath(ctx.reqDir(reqId), 'rtm-accepting.yml')
  const existing = readRTM<RTMAccepting>(filePath)
  const tasks = ctx.tasks(reqId)
  const testCases = parseTestCovers(ctx.testFiles(reqId))
  const taskToTests = buildTaskToTests(tasks, testCases)
  const decomposing = readRTM<RTMDecomposing>(getRTMPath(ctx.reqDir(reqId), 'rtm-decomposing.yml'))
  const frToTasks = decomposing?.traceability?.fr_to_tasks ?? {}
  const frToTests = buildFRToTests(frToTasks, taskToTests, effectiveFRs(ctx, reqId).map(f => f.id))
  const data: RTMAccepting = {
    metadata: ctx.metadata('accepting', reqId, existing),
    inputs: { tasks: tasks.map(t => ({ id: t.id, title: t.title ?? '', status: t.status ?? 'todo' })) },
    outputs: { test_cases: testCases },
    traceability: { task_to_tests: taskToTests, fr_to_tests: frToTests },
    coverage: { testing: calculateTestingCoverage(tasks, taskToTests) },
  }
  writeRTM(filePath, data)
  return data
}
