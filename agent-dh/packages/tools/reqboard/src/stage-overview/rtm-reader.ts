/**
 * StageOverview 的 RTM 读取接口（REQ-260926140539-457b FR-7 / FR-9）。
 *
 * 读取顺序：预构建的 RTM 文件（~1ms）→ 缺失时由 regenerator 实时重建（降级模式）。
 * 任何读取失败返回空块，不抛异常。
 *
 * @module @pi-investment/reqboard/stage-overview/rtm-reader
 */
import { getRTMPath } from '../rtm/file-io.js'
import { readRTM } from '../rtm/file-io.js'
import { requirementsDir } from '../rtm/file-io.js'
import type { RTMAccepting, RTMDecomposing, RTMDesign, RTMLifecycle } from '../rtm/types.js'

/** 读取当前节点 RTM。 */
export function readStageRTM<T = unknown>(workspaceRoot: string, reqId: string, stage: string): T | null {
  return readRTM<T>(getRTMPath(requirementsDir(workspaceRoot, reqId), `rtm-${stage}.yml`))
}

/** 读取全局生命周期 RTM。 */
export function readLifecycleRTM(workspaceRoot: string, reqId: string): RTMLifecycle | null {
  return readRTM<RTMLifecycle>(getRTMPath(requirementsDir(workspaceRoot, reqId), 'rtm-lifecycle.yml'))
}

/** 读取设计节点 RTM。 */
export function readDesignRTM(workspaceRoot: string, reqId: string): RTMDesign | null {
  return readRTM<RTMDesign>(getRTMPath(requirementsDir(workspaceRoot, reqId), 'rtm-design.yml'))
}

/** 读取拆分节点 RTM。 */
export function readDecomposingRTM(workspaceRoot: string, reqId: string): RTMDecomposing | null {
  return readRTM<RTMDecomposing>(getRTMPath(requirementsDir(workspaceRoot, reqId), 'rtm-decomposing.yml'))
}

/** 读取验收节点 RTM。 */
export function readAcceptingRTM(workspaceRoot: string, reqId: string): RTMAccepting | null {
  return readRTM<RTMAccepting>(getRTMPath(requirementsDir(workspaceRoot, reqId), 'rtm-accepting.yml'))
}
