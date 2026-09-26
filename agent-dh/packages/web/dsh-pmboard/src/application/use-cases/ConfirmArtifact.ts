/**
 * ConfirmArtifact 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineConfirmArtifactTool / reqboard_confirm_artifact 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/ConfirmArtifact
 */
import type { UseCaseDeps } from '../ports.js'
import { coverageGateOf, syncRTMYaml } from '../internal/rtm-yaml.js'
import {
  ALL_ARTIFACT_KINDS,
  normalizeText,
} from '../../shared/protocol.js'
import { openRequirementsFor } from '../internal/window.js'
import { fmt } from '../../domain/text/fmt.js'
import { envelope } from '../internal/gate-feedback.js'
import { artifactsToConfirm } from '../internal/artifact-gates.js'
import { checkDesignDecompositionGate } from '../internal/content-gate-wiring.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
} from '../internal/support.js'

export async function confirmArtifact(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; target?: unknown; kind?: unknown; evidence?: unknown }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const targetKind = normalizeText(a.target, 'target', 32)
      const kindRaw = normalizeText(a.kind, 'kind', 64)
      const evidence = normalizeText(a.evidence, 'evidence', 2000)
      if (evidence.length === 0) {
        reject(
          'reqboard_confirm_artifact 未执行：必须附 evidence（用户在 ask_user_question 中的答复原文）'
          + '——会话确认靠它留痕可审计',
          'REQBOARD_INVALID_INPUT',
        )
      }
      // 文字确认核验（REQ-2e9473 t10 三通道③）：evidence 必须引用时间窗内真实存在的
      // 用户消息原文——agent 转述"用户同意了"不算数，系统要能独立见证用户意志。
      // 弹框答复请走 reqboard_ask_confirm（系统直接见证，免 evidence 引证）。
      let evidenceVerified: boolean | undefined
      // 端口封装核验通道：undefined = 缓冲未注入（搬迁前 deps.recentUserMsgs === undefined → 放行并标注）；
      // 返回结构 = 命中/未命中（含 reason）。时间窗由适配器内部统一（CONFIRM_EVIDENCE_WINDOW_MS），此处传值仅占位。
      const check = deps.session.matchesRecentUserMessage(windowKey, evidence, 60 * 60 * 1000)
      if (check !== undefined) {
        if (!check.ok) {
          // REQ-260924213231-b1c4 FR-2/I-9：文案走统一信封（what —— why。补齐：how），判定不动。
          reject(
            envelope({
              lead: 'reqboard_confirm_artifact 未执行：',
              what: '文字确认证据「' + evidence.slice(0, 60) + '」',
              why: '核验失败——' + check.reason + '（未命中该窗口真实用户消息）',
              how: '引用用户最近真实消息原文重调 reqboard_ask_confirm(evidence=...)；或改走弹框路径 reqboard_ask_confirm（系统直接见证，免引证）；兜底由用户在看板一键确认',
            }),
            'REQBOARD_EVIDENCE_FAKE',
          )
        }
        evidenceVerified = true
      }
      if (targetKind !== 'artifact' && targetKind !== 'plan') {
        reject('reqboard_confirm_artifact 未执行：target 只能是 artifact 或 plan', 'REQBOARD_INVALID_INPUT')
      }
      if (targetKind === 'artifact' && !(ALL_ARTIFACT_KINDS as readonly string[]).includes(kindRaw)) {
        reject(
          'reqboard_confirm_artifact 未执行：kind 必须是 ' + ALL_ARTIFACT_KINDS.join(' / '),
          'REQBOARD_INVALID_INPUT',
        )
      }

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_confirm_artifact 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const targetReq = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (targetReq === undefined) {
        reject(
          'reqboard_confirm_artifact 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求',
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }

      // ── REQ-2d1c74 FR-3：确认 kind=design 落章前扫描拆分内容（三通道之一：文字证据）──
      if (targetKind === 'artifact' && kindRaw === 'design') {
        const scan = await checkDesignDecompositionGate(deps.docs, targetReq)
        if (scan !== undefined) reject(fmt('reqboard_confirm_artifact 未执行：{msg}', { msg: scan.message }), scan.code)
      }

      // ── 门禁预检（FR-2 触发点 5 / FR-5）：实施覆盖度必须 100% 才允许批准计划 ──
      // 覆盖度来自 rtm-decomposing.yml（设计章节 → 台账任务）。⚠️ 本构建里"批准计划"先于
      // "拆分落库"，故此时台账通常还没有任务 → total=0 不拦截（coverageGateOf 的边界语义）；
      // 只有在任务已先落库的流程下才真正执法。这一数据流限制见验收文档"已知缺口"。
      // 存量/直种需求（artifacts 为空）豁免——与本仓既有口径一致。
      if (targetKind === 'plan' && (targetReq.artifacts ?? []).length > 0) {
        const planGateProbe = syncRTMYaml(deps, targetReq.id, 'confirm:plan')
        const implGate = coverageGateOf('decomposing', planGateProbe)
        if (implGate !== undefined && !implGate.passed) {
          reject(
            'reqboard_confirm_artifact(target=plan) 被实施覆盖度门禁拒绝：' + (implGate.message ?? '实施覆盖度不足')
              + '。请为缺少任务的设计章节补上覆盖任务后重新提交计划。',
            'REQBOARD_IMPLEMENTATION_COVERAGE_GATE',
          )
        }
      }

      const nowTs = deps.clock.now()
      const result = await deps.repo.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === targetReq.id)
        if (req === undefined) return undefined
        if (targetKind === 'artifact') {
          // REQ-2d1c74 FR-2：kind=design 成组落章（全部 design 产物一次确认）
          const arts = artifactsToConfirm(req, kindRaw as never)
          if (arts.length === 0) {
            reject(
              'reqboard_confirm_artifact 未执行：需求 ' + req.id + ' 没有 kind=' + kindRaw
              + ' 的产物（请先提交该阶段产物）',
              'REQBOARD_MISSING_ARTIFACT',
            )
          }
          for (const art of arts) {
            art.confirmedAt = nowTs
            art.confirmedBy = { kind: 'human', sessionId: windowKey }
            art.confirmedVia = 'session'
            art.confirmedEvidence = evidence
          }
          req.comments.push({
            id: deps.ids.comment(),
            body: fmt('[产物确认·会话] 人经 ask_user_question 确认产物（kind={kind}{group}）：{paths}\n答复原文：{ev}', {
              kind: kindRaw,
              group: arts.length > 1 ? fmt('，成组确认 {n} 份', { n: arts.length }) : '',
              paths: arts.map(x => x.path).join('、'),
              ev: evidence,
            }),
            createdAt: nowTs,
            createdBy: { kind: 'human', sessionId: windowKey },
          })
        } else {
          if (req.plan === undefined) {
            reject('reqboard_confirm_artifact 未执行：需求 ' + req.id + ' 还没有拆分计划', 'REQBOARD_MISSING_PLAN')
          }
          req.plan.approvedAt = nowTs
          req.plan.approvedBy = { kind: 'human', sessionId: windowKey }
          req.plan.approvedVia = 'session'
          req.plan.approvedEvidence = evidence
          delete req.plan.rejectedAt
          delete req.plan.rejectedReason
          req.comments.push({
            id: deps.ids.comment(),
            body:
              '[计划] 已批准（会话确认）：' + req.plan.tasks.length + ' 个任务'
              + '\n答复原文：' + evidence,
            createdAt: nowTs,
            createdBy: { kind: 'human', sessionId: windowKey },
          })
        }
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'human', sessionId: windowKey }
        return { requirements: [req] }
      })
      const changed = (result.changed.requirements ?? [])[0]
      if (changed === undefined) reject('reqboard_confirm_artifact 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // RTM 触发点 3/5：确认产物 / 批准计划 → 对应 RTM 落章
      syncRTMYaml(deps, changed.id, targetKind === 'artifact' ? 'confirm:artifact' : 'confirm:plan')
      return {
        success: true,
        requirement_id: changed.id,
        target: targetKind,
        kind: targetKind === 'artifact' ? kindRaw : '',
        via: 'session',
        ...(evidenceVerified === true ? { evidence_verified: true } : {}),
        note: (targetKind === 'artifact'
          ? '产物已确认（via=session），对应门已放行'
          : '计划已批准（via=session），可用 reqboard_move 推进到 decomposing')
          + (evidenceVerified === true ? '；文字确认已核验（命中真实用户消息）' : '；⚠️ 文字确认核验未启用（recentUserMsgs 未注入）——建议改用 reqboard_ask_confirm'),
      }
    }
