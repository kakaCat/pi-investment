/**
 * Submit RTM 集成辅助函数（REQ-260925172227-2d61）
 * 为 SubmitVerification 用例提供从 FR 文件生成验收追踪
 */
import { RTMManager } from '../../../../../tools/reqboard/src/rtm/rtm-manager.js'
import { scanFRDirectory } from '../../../../../tools/reqboard/src/rtm/fr-parser.js'
import type { AcceptanceTracking } from '../../../../../tools/reqboard/src/types/rtm.js'

export interface SubmitRTMResult {
  acceptance_tracking: AcceptanceTracking[]
  acceptance_tracking_count: number
  /** 是否为返工续验（只生成上版 failed 的项） */
  is_rework: boolean
}

/**
 * 生成验收追踪数据
 * @param reqDir 需求目录（如 docs/requirements/REQ-xxx）
 * @param prevTracking 上一版的验收追踪（返工时只生成 failed 项）
 * @returns 验收追踪数据
 */
export function generateAcceptanceTracking(
  reqDir: string,
  prevTracking?: AcceptanceTracking[]
): SubmitRTMResult {
  // 1. 扫描 FR 文件
  const frMetadata = scanFRDirectory(reqDir)
  
  // 2. 判断是否为返工（上一版有 failed 项）
  const failedItems = prevTracking?.filter(t => t.status === 'failed') ?? []
  const isRework = failedItems.length > 0
  
  // 3. 生成验收追踪
  let acceptanceTracking: AcceptanceTracking[]
  
  if (isRework) {
    // 返工：只生成上版 failed 的项
    acceptanceTracking = failedItems.map(item => ({
      ...item,
      status: 'pending' as const,
      evidence: null,
      judged_at: null,
      judged_by: null,
      // 保留 user_feedback（返工原因）
    }))
  } else {
    // 首次验收：生成所有 FR 的验收项
    acceptanceTracking = RTMManager.fillAcceptanceTracking(frMetadata)
  }
  
  return {
    acceptance_tracking: acceptanceTracking,
    acceptance_tracking_count: acceptanceTracking.length,
    is_rework: isRework
  }
}
