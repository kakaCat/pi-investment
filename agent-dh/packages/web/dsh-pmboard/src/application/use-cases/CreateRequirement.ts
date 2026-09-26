/**
 * CreateRequirement 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineCreateTool / reqboard_create 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * REQ-260924213231-b1c4 T-10（FR-7 / UC-4）：降级路径（弹框通道不可用、用户文字取值）补齐第四问——
 * `doc_location` 入参 → 台账 `docBasePath`；缺省/空串显式回落默认位置并在返回体 `defaults_used` 留痕；
 * 形态非法（绝对路径 / 含 `..`）→ `REQBOARD_INVALID_INPUT`，不静默改路径。
 *
 * @module dsh-pmboard/application/use-cases/CreateRequirement
 */
import type { UseCaseDeps } from '../ports.js'
import { syncRTMYaml } from '../internal/rtm-yaml.js'
import {
  asReqCategory,
  normalizeText,
  normalizeTitle,
} from '../../shared/protocol.js'
import { CAPTURE_QUESTION_IDS } from '../internal/capture-mapping.js'
import {
  agentIdFromExec,
  requireLiveDriver,
  requireDirectHuman,
  createRequirementDirect,
  resolveDocBasePath,
} from '../internal/support.js'

export async function executeCreateRequirement(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      requireDirectHuman(deps, exec)
      const a = (args ?? {}) as { title?: unknown; category?: unknown; summary?: unknown; reason?: unknown; prompt_difficulty?: unknown; doc_location?: unknown }
      const title = normalizeTitle(a.title)
      const category = asReqCategory(a.category)
      const summary = normalizeText(a.summary, 'summary')
      const reason = normalizeText(a.reason, 'reason')
      const promptDifficulty = typeof a.prompt_difficulty === 'string' ? a.prompt_difficulty : 'standard'
      // 第四问（FR-7）：取值 + 回落标记；非法形态在写台账之前响亮失败（不静默改路径）。
      const doc = resolveDocBasePath(a.doc_location)
      const req = await createRequirementDirect(deps, windowKey, {
        title,
        category,
        description: summary.length > 0 ? summary : title,
        reason,
        promptDifficulty,
        docBasePath: doc.docBasePath,
      })
      // RTM 触发点 1（REQ-260926140539-457b FR-2）：立项即落 rtm-lifecycle.yml 骨架（失败不阻断立项）
      syncRTMYaml(deps, req.id, 'create')
      const defaultsUsed = doc.usedDefault ? [CAPTURE_QUESTION_IDS.doc_location] : []
      return {
        success: true,
        requirement_id: req.id,
        title: req.title,
        category: req.category ?? category,
        status: req.status,
        // 与台账同源（createRequirementDirect 已把回落值写进记录）：返回值 / 台账 / 输入包三面一致。
        doc_location: req.docBasePath ?? doc.docBasePath,
        defaults_used: defaultsUsed,
        note: doc.usedDefault
          ? `已直接立项（创建即立项）：REQ 已在看板 draft 泳道立即可见，本窗口已绑定。未提供 doc_location → 已回落默认文档位置 ${doc.docBasePath}（见 defaults_used，不静默猜）。`
          : `已直接立项（创建即立项）：REQ 已在看板 draft 泳道立即可见，本窗口已绑定。文档位置：${doc.docBasePath}。`,
        board_link: `/dashboard#pmboard?req=${req.id}`,
      }
    }
