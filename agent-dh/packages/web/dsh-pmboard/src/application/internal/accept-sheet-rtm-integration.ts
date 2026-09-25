/**
 * AcceptSheet RTM 集成辅助函数（REQ-260925172227-2d61）
 * 为 AcceptSheet 用例提供验收门禁检查和自动归档判定
 */
import { AcceptanceGate } from '../../../../../tools/reqboard/src/rtm/acceptance-gate.js'
import type { AcceptanceTracking } from '../../../../../tools/reqboard/src/types/rtm.js'
import type { VerificationSheet } from '../../shared/protocol.js'

export interface AcceptSheetRTMResult {
  gate_check: {
    total: number
    passed: number
    failed: number
    pending: number
    pass_rate: number
    gate_status: 'passed' | 'blocked' | 'pending'
  }
  should_archive: boolean
}

/**
 * 检查验收门禁
 * @param sheet 验收单（包含所有验收项的状态）
 * @returns 门禁检查结果和是否应该自动归档
 */
export function checkAcceptanceGate(
  sheet: VerificationSheet | undefined
): AcceptSheetRTMResult {
  if (sheet === undefined || sheet.items.length === 0) {
    // 无验收单，返回默认值
    return {
      gate_check: {
        total: 0,
        passed: 0,
        failed: 0,
        pending: 0,
        pass_rate: 0,
        gate_status: 'pending'
      },
      should_archive: false
    }
  }

  // 将验收单转换为 AcceptanceTracking 格式
  const acceptanceTracking: AcceptanceTracking[] = sheet.items.map(item => ({
    acceptance_id: item.id,
    fr_id: item.source.kind === 'requirement' ? 'REQ-LEVEL' : (item.source.taskId ?? 'UNKNOWN'),
    description: item.criterion,
    verification: item.howToVerify ?? item.criterion,
    status: item.status,
    evidence: item.evidence ?? null,
    judged_at: item.decidedAt ?? null,
    judged_by: item.decidedBy?.sessionId ?? null,
    user_feedback: item.opinion ?? null
  }))

  // 调用 AcceptanceGate 检查门禁
  const gateResult = AcceptanceGate.checkGate(acceptanceTracking)
  const shouldArchive = AcceptanceGate.shouldAutoArchive(gateResult)

  return {
    gate_check: {
      total: gateResult.total,
      passed: gateResult.passed,
      failed: gateResult.failed,
      pending: gateResult.pending,
      pass_rate: gateResult.pass_rate,
      gate_status: gateResult.gate_status
    },
    should_archive: shouldArchive
  }
}
