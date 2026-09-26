/**
 * rtm-brainstorming.yml 生成（REQ-260926140539-457b FR-2 触发点 2/3）。
 *
 * 产出：本节点提取的 FR 列表 + 需求文档产物的确认状态。
 *
 * @module @pi-investment/reqboard/rtm/brainstorming-generator
 */
import { getRTMPath, readRTM, writeRTM } from './file-io.js'
import type { RTMContext } from './context.js'
import type { RTMBrainstorming } from './types.js'

/** 生成/更新 rtm-brainstorming.yml。 */
export function generateBrainstormingRTM(ctx: RTMContext, reqId: string): RTMBrainstorming {
  const filePath = getRTMPath(ctx.reqDir(reqId), 'rtm-brainstorming.yml')
  const existing = readRTM<RTMBrainstorming>(filePath)
  const frs = ctx.requirementFRs(reqId)
  const req = ctx.requirement(reqId)
  const reqArtifacts = (req?.artifacts ?? []).filter(a => a.kind === 'requirement')

  const data: RTMBrainstorming = {
    metadata: ctx.metadata('brainstorming', reqId, existing),
    outputs: { requirements: frs },
    status: {
      artifacts: reqArtifacts.map(a => ({
        kind: a.kind,
        path: a.path,
        confirmed: a.confirmedAt !== undefined,
        ...(a.confirmedAt !== undefined ? { confirmed_at: ctx.iso(a.confirmedAt) } : {}),
      })),
    },
  }
  writeRTM(filePath, data)
  return data
}
