/**
 * 把 RTM 追溯数据装配进 StageOverview（REQ-260926140539-457b FR-7）。
 *
 * 输出**加性**块 { traceability, coverage }，调用方（dsh-pmboard 的节点查询）
 * 直接展开进既有响应即可，不需要理解 RTM 文件布局。
 * RTM 缺失且提供了 regenerator 时先实时重建再读（FR-9 降级模式）。
 *
 * @module @pi-investment/reqboard/stage-overview/assembler
 */
import type { RTMGenerator } from '../rtm/generator.js'
import type { StageOverviewTraceability, Traceability } from '../rtm/types.js'
import {
  readAcceptingRTM,
  readDecomposingRTM,
  readDesignRTM,
} from './rtm-reader.js'

/** 装配入参。 */
export interface AssembleStageOverviewInput {
  workspaceRoot: string
  reqId: string
  /** 缺失时用于实时重建（可选；不传则只读不写）。 */
  regenerator?: RTMGenerator
  /** 需要重建时应当生成哪些节点文件（默认 design/decomposing/accepting）。 */
  rebuildStages?: readonly string[]
}

/** 判断追溯块是否"空"（三张映射都为空）。 */
function isEmptyTrace(trace: Traceability): boolean {
  const keys: Array<keyof Traceability> = ['fr_to_design', 'design_to_tasks', 'task_to_tests', 'fr_to_tasks', 'fr_to_tests']
  return keys.every(k => {
    const m = trace[k]
    return m === undefined || Object.keys(m).length === 0
  })
}

/** 装配 StageOverview 的追溯 + 覆盖度块。 */
export function assembleStageOverviewRTM(input: AssembleStageOverviewInput): StageOverviewTraceability {
  const { workspaceRoot, reqId } = input
  let design = readDesignRTM(workspaceRoot, reqId)
  let decomposing = readDecomposingRTM(workspaceRoot, reqId)
  let accepting = readAcceptingRTM(workspaceRoot, reqId)

  const traceability: Traceability = {
    fr_to_design: design?.traceability?.fr_to_design ?? {},
    design_to_tasks: decomposing?.traceability?.design_to_tasks ?? {},
    fr_to_tasks: decomposing?.traceability?.fr_to_tasks ?? {},
    task_to_tests: accepting?.traceability?.task_to_tests ?? {},
    fr_to_tests: accepting?.traceability?.fr_to_tests ?? {},
  }

  if (isEmptyTrace(traceability) && input.regenerator !== undefined) {
    try {
      const stages = input.rebuildStages ?? ['design', 'decomposing', 'accepting']
      for (const stage of stages) {
        if (stage === 'design') input.regenerator.generateDesign(reqId)
        else if (stage === 'decomposing') input.regenerator.generateDecomposing(reqId)
        else if (stage === 'accepting') input.regenerator.generateAccepting(reqId)
      }
      design = readDesignRTM(workspaceRoot, reqId)
      decomposing = readDecomposingRTM(workspaceRoot, reqId)
      accepting = readAcceptingRTM(workspaceRoot, reqId)
      traceability.fr_to_design = design?.traceability?.fr_to_design ?? {}
      traceability.design_to_tasks = decomposing?.traceability?.design_to_tasks ?? {}
      traceability.fr_to_tasks = decomposing?.traceability?.fr_to_tasks ?? {}
      traceability.task_to_tests = accepting?.traceability?.task_to_tests ?? {}
      traceability.fr_to_tests = accepting?.traceability?.fr_to_tests ?? {}
    } catch {
      /* 降级失败保持空块，不打断 StageOverview */
    }
  }

  return {
    traceability,
    coverage: {
      ...(design?.coverage?.design !== undefined ? { design: design.coverage.design } : {}),
      ...(decomposing?.coverage?.implementation !== undefined
        ? { implementation: decomposing.coverage.implementation }
        : {}),
      ...(accepting?.coverage?.testing !== undefined ? { testing: accepting.coverage.testing } : {}),
    },
  }
}
