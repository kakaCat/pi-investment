/**
 * rtm-decomposing.yml 生成（REQ-260926140539-457b FR-2 触发点 5）。
 *
 * 产出：任务列表、设计 → 任务 / FR → 任务映射、实施覆盖度。
 *
 * @module @pi-investment/reqboard/rtm/decomposing-generator
 */
import { getRTMPath, readRTM, writeRTM } from './file-io.js'
import type { RTMContext } from './context.js'
import { buildDesignToTasks, buildFRToDesign, buildFRToTasks } from './traceability-builder.js'
import { calculateImplementationCoverage } from './coverage-calculator.js'
import { effectiveFRs } from './design-generator.js'
import type { DesignSection, RTMDecomposing, RTMDesign } from './types.js'

/** 取设计章节：优先 rtm-design.yml，退回实时解析。 */
export function effectiveSections(ctx: RTMContext, reqId: string): DesignSection[] {
  const d = readRTM<RTMDesign>(getRTMPath(ctx.reqDir(reqId), 'rtm-design.yml'))
  const cached = d?.outputs?.design_sections
  if (Array.isArray(cached) && cached.length > 0) return cached
  return []
}

/** 生成/更新 rtm-decomposing.yml。 */
export function generateDecomposingRTM(ctx: RTMContext, reqId: string): RTMDecomposing {
  const filePath = getRTMPath(ctx.reqDir(reqId), 'rtm-decomposing.yml')
  const existing = readRTM<RTMDecomposing>(filePath)
  const frs = effectiveFRs(ctx, reqId)
  const sections = effectiveSections(ctx, reqId)
  const tasks = ctx.tasks(reqId)
  const designToTasks = buildDesignToTasks(sections, tasks)
  const frToTasks = buildFRToTasks(buildFRToDesign(frs, sections), designToTasks, frs.map(f => f.id))
  const data: RTMDecomposing = {
    metadata: ctx.metadata('decomposing', reqId, existing),
    inputs: { requirements: frs, design_sections: sections },
    outputs: {
      tasks: tasks.map(t => ({
        id: t.id,
        title: t.title ?? '',
        implements: t.implements ?? '',
        serves: t.serves ?? [],
        depends_on: t.depends_on ?? [],
        phase: t.phase ?? '',
        side: t.side ?? '',
      })),
    },
    traceability: { design_to_tasks: designToTasks, fr_to_tasks: frToTasks },
    coverage: { implementation: calculateImplementationCoverage(sections, designToTasks) },
  }
  writeRTM(filePath, data)
  return data
}
