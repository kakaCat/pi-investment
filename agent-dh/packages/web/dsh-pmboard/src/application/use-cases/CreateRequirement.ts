/**
 * CreateRequirement 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineCreateTool / reqboard_create 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/CreateRequirement
 */
import type { UseCaseDeps } from '../ports.js'
import {
  asReqCategory,
  normalizeText,
  normalizeTitle,
} from '../../shared/protocol.js'
import {
  agentIdFromExec,
  requireLiveDriver,
  requireDirectHuman,
  createRequirementDirect,
} from '../internal/support.js'

export async function executeCreateRequirement(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      requireDirectHuman(deps, exec)
      const a = (args ?? {}) as { title?: unknown; category?: unknown; summary?: unknown; reason?: unknown; prompt_difficulty?: unknown }
      const title = normalizeTitle(a.title)
      const category = asReqCategory(a.category)
      const summary = normalizeText(a.summary, 'summary')
      const reason = normalizeText(a.reason, 'reason')
      const promptDifficulty = typeof a.prompt_difficulty === 'string' ? a.prompt_difficulty : 'standard'
      const req = await createRequirementDirect(deps, windowKey, {
        title,
        category,
        description: summary.length > 0 ? summary : title,
        reason,
        promptDifficulty,
      })
      return {
        success: true,
        requirement_id: req.id,
        title: req.title,
        category: req.category ?? category,
        status: req.status,
        note: '已直接立项（创建即立项）：REQ 已在看板 draft 泳道立即可见，本窗口已绑定',
        board_link: `/dashboard#pmboard?req=${req.id}`,
      }
    }
