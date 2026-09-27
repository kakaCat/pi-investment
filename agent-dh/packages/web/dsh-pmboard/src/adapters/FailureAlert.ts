/**
 * 失败告警适配器（REQ-4842fe t8 / FR-13）：高优告警的唯一实现。
 *
 * 【2026-XX-XX 全面Dive化】
 * 移除会话投递通道，只保留日志告警。
 * Dive模式下失败告警通过日志和看板状态体现，不再推送到inbox。
 *
 * @module dsh-pmboard/adapters/FailureAlert
 */
import type { FailureAlertPort } from '../application/ports.js'
import { fmt } from '../domain/text/fmt.js'

export interface FailureAlertWiring {
  log: (message: string) => void
  /** 需求来源窗口查询（用于日志记录） */
  windowFor: (requirementId: string) => string | undefined
}

export function createFailureAlert(wire: FailureAlertWiring): FailureAlertPort {
  return {
    alert: ({ requirementId, title, content }) => {
      const raw = fmt('{title}\n{content}', { title, content })
      try { 
        wire.log(raw) 
      } catch { 
        /* 日志失败不阻断（宿主日志记原始正文，排障用） */ 
      }
      
      // 记录窗口信息用于调试
      try {
        const windowKey = wire.windowFor(requirementId)
        if (windowKey !== undefined && windowKey.length > 0) {
          wire.log(fmt('需求 {req} 失败告警（窗口: {wk}）', { req: requirementId, wk: windowKey }))
        }
      } catch { 
        /* 查询失败不阻断 */ 
      }
    },
  }
}