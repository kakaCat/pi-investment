/**
 * rtm-design.yml 生成（REQ-260926140539-457b FR-2 触发点 4）。
 *
 * 产出：设计章节（含 serves 标注）、FR → 设计映射、设计覆盖度。
 *
 * @module @pi-investment/reqboard/rtm/design-generator
 */
import { getRTMPath, readRTM, writeRTM } from './file-io.js'
import type { RTMContext } from './context.js'
import { parseDesignSections } from './parser.js'
import { buildFRToDesign } from './traceability-builder.js'
import { calculateDesignCoverage } from './coverage-calculator.js'
import type { FR, RTMBrainstorming, RTMDesign } from './types.js'

/** 取本需求的 FR：优先 brainstorming RTM，退回实时解析 requirement.md。 */
export function effectiveFRs(ctx: RTMContext, reqId: string): FR[] {
  const brain = readRTM<RTMBrainstorming>(getRTMPath(ctx.reqDir(reqId), 'rtm-brainstorming.yml'))
  const cached = brain?.outputs?.requirements
  if (Array.isArray(cached) && cached.length > 0) return cached
  return ctx.requirementFRs(reqId)
}

/** 生成/更新 rtm-design.yml。 */
export function generateDesignRTM(ctx: RTMContext, reqId: string): RTMDesign {
  const filePath = getRTMPath(ctx.reqDir(reqId), 'rtm-design.yml')
  const existing = readRTM<RTMDesign>(filePath)
  const frs = effectiveFRs(ctx, reqId)
  const sections = parseDesignSections(ctx.designFiles(reqId))
  const frToDesign = buildFRToDesign(frs, sections)
  const data: RTMDesign = {
    metadata: ctx.metadata('design', reqId, existing),
    inputs: { requirements: frs },
    outputs: { design_sections: sections },
    traceability: { fr_to_design: frToDesign },
    coverage: { design: calculateDesignCoverage(frs, frToDesign) },
  }
  writeRTM(filePath, data)
  return data
}
