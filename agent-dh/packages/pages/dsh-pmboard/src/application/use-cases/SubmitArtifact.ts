/**
 * SubmitArtifact 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineRequirementSubmitTool + definePlanSubmitTool 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/SubmitArtifact
 */
import type { UseCaseDeps } from '../ports.js'
import {
  normalizePlanTasks,
  normalizeText,
  type StageArtifact,
} from '../../shared/protocol.js'
import { applyDocSync, clearDocSync, docSyncDownstream } from '../../domain/workflow/DocSyncSpec.js'
import { openRequirementsFor } from '../internal/window.js'
import { registerArtifact } from '../internal/artifact-gates.js'
import { checkNumberChainGate, checkDesignServesGate, checkRequirementDocFormatGate, assertArtifactOpenable } from '../internal/content-gate-wiring.js'
import { missingCategoryDocs } from '../internal/category-doc-sets.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
  notifyArtifactRegistered,
} from '../internal/support.js'

export async function submitRequirementArtifact(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; path?: unknown; summary?: unknown; change_note?: unknown }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const explicitPath = normalizeText(a.path, 'path', 400)
      const summary = normalizeText(a.summary, 'summary', 2000)
      const changeNote = normalizeText(a.change_note, 'change_note', 1000)

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_requirement_submit 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (target === undefined) {
        reject(
          'reqboard_requirement_submit 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求',
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }
      // 阶段纪律：需求文档属于「需求分析」（brainstorming）阶段产物。
      if (target.status !== 'brainstorming') {
        reject(
          'reqboard_requirement_submit 未执行：需求当前处于 ' + target.status
          + '，需求文档只能在 brainstorming 阶段提交（回到需求分析重新提交会作废既有确认）',
          'REQBOARD_BAD_STATUS',
        )
      }

      // REQ-2d1c74 FR-5：登记即可打开性校验——不存在/伪路径/越界当场拒（不再等人点看才发现）。
      // 通过则返回 normalized 工作区相对路径（台账以归一值登记，形态不再漂移）。
      const path = assertArtifactOpenable(
        deps.docs,
        explicitPath.length > 0 ? explicitPath : 'docs/requirements/' + target.id + '/requirement.md',
      )

      // ── 需求文档格式校验（编号规范强制）────────────────────────────────
      // 在 mutate 之前校验：系统负责格式，人负责内容。避免让用户确认不合格的文档。
      const formatFailure = await checkRequirementDocFormatGate(deps.docs, target)
      if (formatFailure !== undefined) {
        reject(formatFailure.message, formatFailure.code)
      }

      const nowTs = deps.clock.now()
      const artifact: StageArtifact = {
        stage: 'brainstorming',
        kind: 'requirement',
        path,
        registeredAt: nowTs,
        registeredBy: { kind: 'agent', sessionId: windowKey },
      }
      // 幂等判定放在 mutate 之前（registerArtifact 内部同样幂等，这里只为 give 准确的 registered 标记）
      const alreadyRegistered = (target.artifacts ?? []).some(
        x => x.stage === artifact.stage && x.kind === artifact.kind && x.path === artifact.path,
      )
      // 文档演进留痕（REQ-2e9473 t19/W8）：已确认过再重写 = 变更 → change_note 必填
      const prevConfirmed = (target.artifacts ?? []).find(
        x => x.kind === 'requirement' && x.confirmedAt !== undefined,
      )
      const isChange = prevConfirmed !== undefined
      if (isChange && changeNote.length === 0) {
        reject(
          'reqboard_requirement_submit 未执行：需求文档此前已经人确认过，重写即变更——'
          + '必须传 change_note（改了哪里/为什么，留痕并把下游标"待同步"）；'
          + '改完全文后再提交，旧确认会作废需重新确认',
          'REQBOARD_CHANGELOG_REQUIRED',
        )
      }
      const result = await deps.repo.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        const added = registerArtifact(req, artifact)
        if (added) {
          req.comments.push({
            id: deps.ids.comment(),
            body:
              '[需求文档] 提交需求文档产物（待人工确认）：' + path
              + (summary.length > 0 ? '\n摘要：' + summary : ''),
            createdAt: nowTs,
            createdBy: { kind: 'agent', sessionId: windowKey },
          })
          req.version += 1
          req.updatedAt = nowTs
          req.updatedBy = { kind: 'agent', sessionId: windowKey }
        }
        if (isChange) {
          // changelog + 作废旧确认 + 下游待同步
          const art = (req.artifacts ?? []).find(x => x.kind === 'requirement')
          if (art !== undefined) {
            delete art.confirmedAt
            delete art.confirmedBy
            delete art.confirmedVia
          }
          // 需求文档变更 → 已登记的 plan / decomposition 待同步（规则在 DocSyncSpec.ts，t3）
          const downstream = docSyncDownstream('requirement', req.artifacts)
          applyDocSync(req, 'requirement', changeNote, nowTs)
          req.comments.push({
            id: deps.ids.comment(),
            body: '[文档变更] 需求文档变更（changelog）：' + changeNote
              + '\n旧确认已作废（需重新确认）；下游待同步：' + (downstream.join('、') || '（暂无）'),
            createdAt: nowTs,
            createdBy: { kind: 'agent', sessionId: windowKey },
          })
          req.version += 1
          req.updatedAt = nowTs
          req.updatedBy = { kind: 'agent', sessionId: windowKey }
        }
        return { requirements: [req] }
      })
      const changed = (result.changed.requirements ?? [])[0]
      if (changed === undefined) reject('reqboard_requirement_submit 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      const registered = !alreadyRegistered
      if (registered) notifyArtifactRegistered(deps, changed.id, artifact)
      return {
        success: true,
        requirement_id: changed.id,
        artifact: { stage: artifact.stage, kind: artifact.kind, path: artifact.path },
        registered,
        note: registered
          ? '需求文档产物已登记。下一步：调 reqboard_ask_confirm（target=artifact, kind=requirement）弹框请人确认——肯定答复自动落章并推进到 design（看板一键确认同样是有效通道）'
          : '该需求文档此前已登记（幂等命中，未重复登记）',
      }
    }

export async function submitPlanArtifact(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; path?: unknown; summary?: unknown; tasks?: unknown; change_note?: unknown }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const path = normalizeText(a.path, 'path', 400)
      const summary = normalizeText(a.summary, 'summary', 4000)
      const changeNote = normalizeText(a.change_note, 'change_note', 1000)
      if (path.length === 0) reject('reqboard_plan_submit 未执行：path 不能为空', 'REQBOARD_INVALID_INPUT')
      if (summary.length === 0) reject('reqboard_plan_submit 未执行：summary 不能为空（人要读它来决定批不批）', 'REQBOARD_INVALID_INPUT')
      // 2026-09-21 用户裁定（w-2105d331 代录）：拆分计划归**拆分阶段**——设计阶段只交
      // 一套设计文档（架构/四视角/风险/工作流划分），拆分计划（含任务表）在 decomposing
      // 阶段提交并批准，批准 = reqboard_decompose 落卡的唯一钥匙。传了 tasks 走严格校验；
      // 不传则合法（tasks=[]，decompose 时走创作路径兜底）。
      const tasks = a.tasks === undefined ? [] : normalizePlanTasks(a.tasks)

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_plan_submit 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (target === undefined) {
        reject(
          'reqboard_plan_submit 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求',
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }
      // 流程纪律（2026-09-21 用户裁定）：拆分计划属于「拆分」（decomposing）阶段——
      // 设计阶段只写设计文档（design/ 目录，G2 确认设计文档后才进拆分）。
      if (target.status !== 'decomposing') {
        reject(
          'reqboard_plan_submit 未执行：需求当前处于 ' + target.status + '，拆分计划只能在 decomposing（拆分）阶段提交。'
          + '设计阶段只写设计文档 → 确认设计文档后进拆分 → 再提交拆分计划；'
          + '已有计划要改，也在拆分阶段重新提交（旧批准自动作废）',
          'REQBOARD_BAD_STATUS',
        )
      }

      // 计划变更留痕（REQ-2e9473 t19/W8）：已批准过再重交 = 变更 → change_note 必填
      const prevPlanApproved = target.plan?.approvedAt !== undefined
      if (prevPlanApproved && changeNote.length === 0) {
        reject(
          'reqboard_plan_submit 未执行：计划此前已获批准，重交即变更——必须传 change_note'
          + '（改了什么/为什么）；旧批准作废需重新批准，下游拆分文档会标"待同步"',
          'REQBOARD_CHANGELOG_REQUIRED',
        )
      }
      // REQ-2d1c74 FR-5：plan path 存在性补齐（现状不查——没落盘的计划也能登记，
      // 用户点看才发现"没有找到文件"）。不存在/伪路径/越界当场拒。
      const openPath = assertArtifactOpenable(deps.docs, path)

      // ── 编号串联门禁（REQ-d3e61a T-4 / FR-2）：serves 不得悬空 ────────────────
      // 悬空（引用了不存在的编号）→ 拒；根编号无下游 → 不拒，随结果返回供看板标红。
      // 放在 mutate 之前：拒绝时不留任何副作用。
      const chain = await checkNumberChainGate(deps.docs, target)
      if (chain.failure !== undefined) {
        reject(chain.failure.message, chain.failure.code)
      }
      // FR-5：每个设计章节都必须标注服务哪条功能点（缺标注 = 孤儿章节）
      const designServes = await checkDesignServesGate(deps.docs, target)
      if (designServes !== undefined) {
        reject(designServes.message, designServes.code)
      }
      // ── 分类文档集（REQ-d3e61a T-13 / FR-15）：立项类型决定要哪些文档、每份写什么必填节 ──
      // 类型只能减少文档**数量**，不能取消**追溯**——故每个类型都要求根文档的必填节。
      {
        const reqDir = 'docs/requirements/' + target.id
        const rootPath = reqDir + '/requirement.md'
        const rootExists = deps.docs.exists(rootPath)
        const rootText = rootExists ? await deps.docs.read(rootPath) : ''
        const designDir = reqDir + '/design'
        const designNames = (deps.docs.list?.(designDir) ?? [])
          .filter(e => e.isFile !== false)
          .map(e => e.name ?? '')
        const missingDocs = missingCategoryDocs({ category: target.category, rootExists, rootText, designNames })
        if (missingDocs.length > 0) {
          reject(
            'reqboard_plan_submit 未执行：' + target.category + ' 类型的必填文档未交齐——'
            + missingDocs.join('；') + '。类型只减少文档数量，不取消追溯；确实不适用的请在需求文档 §8 边界写明理由',
            'REQBOARD_MISSING_REQUIRED_DOC',
          )
        }
      }

      const nowTs = deps.clock.now()
      const result = await deps.repo.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        if (prevPlanApproved) {
          // 计划变更 → 下游 decomposition 待同步 + changelog（规则在 domain/workflow/DocSyncSpec.ts，t3）
          applyDocSync(req, 'plan', changeNote, nowTs)
          const downstream = docSyncDownstream('plan', req.artifacts)
          req.comments.push({
            id: deps.ids.comment(),
            body: '[文档变更] 设计（拆分计划）变更：' + changeNote
              + '\n旧批准已作废（需重新批准）；下游待同步：' + (downstream.join('、') || '（暂无）'),
            createdAt: nowTs,
            createdBy: { kind: 'agent', sessionId: windowKey },
          })
        }
        // 销标：plan 重交即完成自身同步
        clearDocSync(req, 'plan')
        req.plan = {
          path: openPath,
          summary,
          tasks,
          submittedAt: nowTs,
          submittedBy: { kind: 'agent', sessionId: windowKey },
        }
        req.comments.push({
          id: deps.ids.comment(),
          body:
            '[计划] 提交拆分计划（' + tasks.length + ' 个任务，待人工批准）：' + path
            + '\n摘要：' + summary
            + '\n' + tasks.map(t => '- ' + t.key + ' ' + t.title + ((t.dependsOn ?? []).length > 0 ? '（依赖 ' + (t.dependsOn ?? []).join(', ') + '）' : '')).join('\n'),
          createdAt: nowTs,
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'agent', sessionId: windowKey }
        return { requirements: [req] }
      })
      const changed = (result.changed.requirements ?? [])[0]
      if (changed === undefined) reject('reqboard_plan_submit 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // ── 产物登记（REQ-31e11f t4）：拆分计划 = 拆分阶段的 decomposition 产物 ──
      // （2026-09-21：原 stage=design/kind=plan；kind=decomposition 使 G3「批准拆分计划」门
      //   直接锚定本产物——批准计划即落章 decomposition，无需二次确认拆分清单）
      const planArtifact: StageArtifact = {
        stage: 'decomposing',
        kind: 'decomposition',
        path: openPath,
        registeredAt: nowTs,
        registeredBy: { kind: 'agent', sessionId: windowKey },
      }
      await deps.repo.mutate('requirement-updated', (ledger) => {
        const r = ledger.requirements.find(x => x.id === changed.id)
        if (r === undefined) return undefined
        registerArtifact(r, planArtifact)
        return { requirements: [r] }
      })
      notifyArtifactRegistered(deps, changed.id, planArtifact)
      return {
        success: true,
        requirement_id: changed.id,
        plan_status: 'pending_approval',
        orphan_clauses: chain.orphans,
        task_count: tasks.length,
        tasks: tasks.map(t => ({ key: t.key, title: t.title, depends_on: [...(t.dependsOn ?? [])] })),
        note: '拆分计划已提交' + (tasks.length === 0 ? '（未含任务表——落库时由 reqboard_decompose 传 tasks 创作）' : '（含 ' + tasks.length + ' 张任务卡）')
          + '。下一步：调 reqboard_ask_confirm（target=plan）弹框请人批准——批准后自动拆分落库并进入实施（看板「批准计划」同样是有效通道）',
      }
    }
