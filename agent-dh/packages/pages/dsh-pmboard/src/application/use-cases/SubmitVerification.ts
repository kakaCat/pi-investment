/**
 * SubmitVerification 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineVerifySubmitTool / reqboard_verify_submit 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/SubmitVerification
 */
import type { UseCaseDeps } from '../ports.js'
import { fmt } from '../../domain/text/fmt.js'
import {
  normalizeText,
  type VerificationSheet,
} from '../../shared/protocol.js'
import { buildSheet } from '../../domain/workflow/AcceptanceSheetSpec.js'
import { checkDocCompleteness } from '../../domain/workflow/DocCompleteness.js'
import { renderVerificationDoc } from '../../domain/workflow/VerificationDoc.js'
import { docSyncSummary } from '../../domain/workflow/DocSyncSpec.js'
import { openRequirementsFor } from '../internal/window.js'
import { applyTaskRollup } from '../internal/rollup.js'
import { captureSnapshot } from '../internal/token-usage.js'
import { registerArtifact } from '../internal/artifact-gates.js'
import {
  collectOrphanTestFiles,
  e2eCoverageOf,
  collectNumberedItems,
  collectTaskRefs,
  buildConsistencyRows,
  consistencyGaps,
  assertArtifactOpenable,
} from '../internal/content-gate-wiring.js'
import { checkHowToVerify, checkAcceptance } from '../../domain/task/Acceptability.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
  rollupBlockersOf,
  workspacePathCandidates,
} from '../internal/support.js'

export async function submitVerification(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; summary?: unknown; evidence?: unknown }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const summary = normalizeText(a.summary, 'summary', 2000)
      if (summary.length === 0) reject('reqboard_verify_submit 未执行：summary 不能为空', 'REQBOARD_INVALID_INPUT')
      if (!Array.isArray(a.evidence)) reject('reqboard_verify_submit 未执行：evidence 必须是数组', 'REQBOARD_INVALID_INPUT')
      const evidence = (a.evidence as unknown[])
        .map(e => normalizeText(e, 'evidence[]', 1000))
        .filter(e => e.length > 0)
        .slice(0, 20)
      if (evidence.length === 0) {
        reject('reqboard_verify_submit 未执行：至少要有一条可复核的证据（命令+输出摘要 / 报告路径 / 截图路径）', 'REQBOARD_INVALID_INPUT')
      }
      // evidence 存在性校验（REQ-2e9473 t12）：evidence 里引用的工作区文件路径必须真实存在，
      // 防"编造证据路径"（事故 E 变体：文档/产物路径不存在也算证据）。
      const citedPaths = workspacePathCandidates(evidence)
      const docs = deps.docs
      const missingPaths = citedPaths.filter(p => !docs.exists(p))
      if (missingPaths.length > 0) {
        reject(
          fmt('reqboard_verify_submit 未执行：evidence 引用的文件不存在（疑似编造）：{paths}。请引用真实存在的产物/报告路径，或改用命令+输出摘要', { paths: missingPaths.join('、') }),
          'REQBOARD_EVIDENCE_MISSING',
        )
      }

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_verify_submit 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (target === undefined) {
        reject(fmt('reqboard_verify_submit 未执行：需求 {id} 不是本窗口绑定的进行中需求', { id: explicitId }), 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }
      if (target.status !== 'implementing' && target.status !== 'accepting') {
        reject(fmt('reqboard_verify_submit 未执行：需求处于 {status}，只有执行/验收阶段的交付才能提交验收', { status: target.status }), 'REQBOARD_BAD_STATUS')
      }

      // ── 9 类文档完整性检查（REQ-308b9a FR-7 / AC-7.4、7.5）─────────────────
      // 口径见 domain/workflow/DocCompleteness.ts（与本仓 feature 流水线产物对齐，不另造清单）。
      // 缺项 → **拒绝提交**（"缺文档也能过验收"会让文档永远补不上）。
      const reqDir = 'docs/requirements/' + target.id
      const collectDir = (sub: string): string[] => docs.list(sub.length > 0 ? reqDir + '/' + sub : reqDir)
        .filter(e => e.isFile)
        .map(e => (sub.length > 0 ? sub + '/' + e.name : e.name))
      const reqFiles = new Set<string>([
        ...collectDir(''),
        ...collectDir('design'),
        ...collectDir('tasks'),
        ...collectDir('reviews'),
        ...collectDir('tests'),
      ])
      const reqTaskIds = snapshot.tasks
        .filter(t => t.requirementId === target.id && t.status !== 'canceled')
        .map(t => t.id)
      // 存量/直种需求（artifacts 为空）→ 豁免，不追溯惩罚（同 isLegacyForHow 的口径）；
      // 走新流水线的需求在 requirement/plan/design 各节点已登记产物，故必然被检查。
      // 两条豁免口径（都指向"不是走新流水线落盘的需求"）：
      //   ① artifacts 为空 —— 直种/存量数据，不追溯（同 isLegacyForHow）；
      //   ② 需求目录为空 —— 文档体系根本未建立（测试种子/脏数据）。
      // 真实需求在 brainstorming 必落 requirement.md，故目录非空、必然受检。
      // 判据用**盘上是否有 requirement.md**（稳定信号：本流程第一次提交会写 verification.md，
      // 若用"目录非空"会被自己生成的产物破坏——实测踩过）。真实需求在 brainstorming 必落它。
      const isLegacyForDocs = target.artifacts === undefined || target.artifacts.length === 0 || !reqFiles.has('requirement.md')
      const docCheck = isLegacyForDocs
        ? { passed: true, missing: [] as string[] }
        : checkDocCompleteness({ files: reqFiles, taskIds: reqTaskIds })
      if (!docCheck.passed) {
        reject(
          fmt('reqboard_verify_submit 未执行：验收前置的 9 类文档未齐——{list}。请补齐后再提交验收（AC-7.5）', { list: docCheck.missing.join('、') }),
          'REQBOARD_DOC_INCOMPLETE',
        )
      }

      // ── 孤儿用例检测（REQ-d3e61a T-7 / FR-5）：设计文件点名了、但文件头未声明覆盖的测试文件 ──
      // 警告级：不阻断提交，但必须成为验收面上**可见的一项**（靠人记得 = 不该有的形态）。
      // 必须在 mutate 之前算（读文件是异步的，而 mutate 回调是同步的）。
      // ── 「怎么验」（REQ-d3e61a T-9 / FR-10）：验收项必须能照着动手验 ──────────────
      // 计划期门槛是"含断言词"（VERIFIABLE_ANCHOR），验收期门槛是"能独立复核"（HOW_TO_VERIFY：
      // 命令 / 可查数据 / 可达界面路径）。两层之间的**缝**正是本卡要堵的。
      // 分流（与其它内容闸门同语义）：
      //   ① 存量需求（artifacts 为空）→ 豁免，不追溯惩罚
      //   ② 过了计划期锚点但验收期不可操作 → **硬拦**（须先用 reqboard_task_move 的 acceptance
      //      参数修订——修订通道见 AmendTaskAcceptance.ts，硬拦必须配修复路径，否则是死锁）
      //   ③ 连锚点都没有（直种/历史数据）→ 只作**可见项**，不允许静默
      const isLegacyForHow = target.artifacts === undefined || target.artifacts.length === 0
      const unverifiable: string[] = []
      const hardUnverifiable: string[] = []
      if (!isLegacyForHow) {
        for (const t of snapshot.tasks) {
          if (t.requirementId !== target.id || t.status === 'canceled') continue
          const acceptance = t.acceptance ?? ''
          const key = t.title.length > 0 ? t.title : t.id
          const how = checkHowToVerify(key, acceptance)
          if (how.ok) continue
          if (checkAcceptance(key, acceptance).ok) hardUnverifiable.push(how.reason)
          else unverifiable.push(how.reason)
        }
      }
      if (hardUnverifiable.length > 0) {
        reject(
          fmt('reqboard_verify_submit 未执行：以下验收项无法照着验——{items}。可用 reqboard_task_move(task_id, acceptance=...) 修订（修订通道已就位）', { items: hardUnverifiable.join('；') }),
          'REQBOARD_ACCEPTANCE_NOT_EXECUTABLE',
        )
      }

      const orphanTestFiles = await collectOrphanTestFiles(deps.docs, target)
      // E2E 覆盖读数（FR-11）：读需求文档的测试策略表。读数未知（undefined）时不追加可见项。
      const e2eCoverage = await e2eCoverageOf(deps.docs, target)
      // 三方一致性（FR-9）：做什么（需求编号）× 怎么做（设计章节 serves）× 实际做了什么（任务↔编号绑定）。
      // 绑定从 decomposition.md 的 RTM 表读——没有该表时**不比对**（避免把"没记录"误报成"实施缺失"）。
      const taskRefs = await collectTaskRefs(deps.docs, target)
      const consistency = taskRefs.length === 0
        ? []
        : consistencyGaps(buildConsistencyRows(await collectNumberedItems(deps.docs, target), taskRefs))

      const nowTs = deps.clock.now()
      const result = await deps.repo.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        // ── 逐项验收单生成（REQ-2e9473 t13/W6；规则在 domain/workflow/AcceptanceSheetSpec.ts，t4）──
        // items = 每任务验收标准 + 需求级标准；返工时（上一版有未过项）只含未过项。
        const allTasks = ledger.tasks.filter(t => t.requirementId === req.id && t.status !== 'canceled')
        const prevSheet = req.verification?.sheet
        const built = buildSheet({
          sheetHistoryLength: req.verification?.sheetHistory?.length ?? 0,
          ...(prevSheet !== undefined ? { prevSheet } : {}),
          tasks: allTasks.map(t => ({ id: t.id, title: t.title, acceptance: t.acceptance })),
          evidence,
          ...(orphanTestFiles.length > 0 ? { orphanTestFiles } : {}),
          ...(unverifiable.length > 0 ? { unverifiableItems: unverifiable } : {}),
          ...(e2eCoverage !== undefined ? { e2eCoverage } : {}),
          ...(consistency.length > 0 ? { consistencyGaps: consistency } : {}),
          generatedAt: nowTs,
          generatedBy: { kind: 'agent', sessionId: windowKey },
        })
        const sheet: VerificationSheet = built.sheet as VerificationSheet
        req.verification = {
          summary,
          evidence,
          submittedAt: nowTs,
          submittedBy: { kind: 'agent', sessionId: windowKey },
          sheet,
          sheetHistory: [
            ...(req.verification?.sheetHistory ?? []),
            ...(prevSheet !== undefined ? [prevSheet] : []),
          ],
        }
        req.comments.push({
          id: deps.ids.comment(),
          body: fmt('[验收] 提交验收材料（待人工审核）：{summary}\n证据：\n{evidence}', {
            summary,
            evidence: evidence.map(e => '- ' + e).join('\n'),
          }),
          createdAt: nowTs,
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'agent', sessionId: windowKey }
        // 任务全完成时顺带推进到验收态（人来了就有东西可审）
        const advanced = applyTaskRollup(
          ledger,
          { now: nowTs, commentId: () => deps.ids.comment(), snapshot: () => captureSnapshot(deps, windowKey) },
          req.id,
        )
        return { requirements: [req, ...advanced] }
      })
      const changed = (result.changed.requirements ?? [])[0]
      if (changed === undefined) reject('reqboard_verify_submit 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // ── 产物登记（REQ-31e11f t4）：verification 产物 ─────────────────────
      // ── verification.md 结构化生成（FR-7 / AC-7.1~7.3）────────────────────
      // 四段：验收列表（含派生操作步骤/预期结果）· 测试报告 · 文档完整性检查 · 验收结果表。
      const verPath = reqDir + '/verification.md'
      const sheetNow = changed.verification?.sheet
      const ledgerTasks = deps.repo.snapshot().tasks
        .filter(t => t.requirementId === target.id && t.status !== 'canceled')
      const taskById = new Map(ledgerTasks.map(t => [t.id, t]))
      const docItems = (sheetNow?.items ?? []).map(it => {
        const src = it.source
        const t = src.kind === 'task' ? taskById.get(src.taskId) : undefined
        const who = it.decidedBy === undefined
          ? undefined
          : [it.decidedBy.kind, it.decidedBy.sessionId].filter(v => v !== undefined && v !== '').join('/')
        return {
          id: it.id,
          title: src.kind === 'task' ? (t?.title ?? src.taskId) : '需求级验收',
          criterion: it.criterion,
          howToVerify: src.kind === 'task' ? (t?.acceptance ?? it.criterion) : it.criterion,
          status: it.status,
          ...(it.opinion !== undefined ? { opinion: it.opinion } : {}),
          ...(who !== undefined ? { decidedBy: who } : {}),
          ...(it.decidedAt !== undefined ? { decidedAt: it.decidedAt } : {}),
        }
      })
      await docs.write(verPath, renderVerificationDoc({
        reqId: target.id,
        title: target.title,
        summary,
        sheetVersion: sheetNow?.version ?? 1,
        items: docItems as never,
        testReport: evidence,
        docCheck,
      }))
      // REQ-2d1c74 FR-5：写盘后核验可打开性——写盘静默失败时当场响亮，而不是登记一个不存在的产物
      assertArtifactOpenable(deps.docs, verPath)
      await deps.repo.mutate('requirement-updated', (ledger) => {
        const r = ledger.requirements.find(x => x.id === changed.id)
        if (r === undefined) return undefined
        registerArtifact(r, {
          stage: 'accepting', kind: 'verification', path: verPath,
          registeredAt: nowTs, registeredBy: { kind: 'agent', sessionId: windowKey },
        })
        return { requirements: [r] }
      })
      const ledgerNow = deps.repo.snapshot()
      const tasks = ledgerNow.tasks.filter(t => t.requirementId === target.id && t.status !== 'canceled')
      const reqNow = ledgerNow.requirements.find(r => r.id === changed.id)
      // rollup 阻塞显式化（REQ-2e9473 t02）：有未完成任务时验收材料虽收，但需求进不了 accepting
      const blockers = reqNow === undefined ? undefined : rollupBlockersOf(ledgerNow, reqNow.id, reqNow.status)
      // 说明文案与变量**在 return 之外**组装：输出契约门禁静态扫描 return 字面量的顶层键，
      // 把 fmt 的变量表误读成响应字段（实测被误判为 n/list 两个未声明字段）。不改门禁，改写法。
      const blockerBlock = blockers === undefined
        ? {}
        : {
            blockers,
            warning: fmt('⚠️ 需求未进验收（rollup 阻塞）：{n} 个任务未完成——{list}。若为重复拆分产生的幽灵任务，请人工取消后重新提交', {
              n: blockers.length,
              list: blockers.map(b => b.id + ' ' + b.title + '（' + b.status + '）').join('；'),
            }),
          }
      const finishNote = blockers === undefined
        ? '验收材料已提交。下一步：调 reqboard_ask_confirm（target=artifact, kind=verification）弹框请人逐项审核（看板「验收通过/退回」同样是有效通道）'
        : fmt('验收材料已提交，但需求因 {n} 个未完成任务停在 implementing——见 warning/blockers', { n: blockers.length })
      return {
        success: true,
        requirement_id: changed.id,
        status: reqNow?.status ?? changed.status,
        tasks_done: tasks.filter(t => t.status === 'done').length,
        tasks_total: tasks.length,
        sheet_version: reqNow?.verification?.sheet?.version ?? 0,
        sheet_items: reqNow?.verification?.sheet?.items.length ?? 0,
        ...(reqNow?.verification?.sheet?.reworkOnly === true ? { rework_only: true } : {}),
        ...(reqNow !== undefined && (reqNow.docSyncPending ?? []).length > 0
          ? { doc_sync_pending: reqNow.docSyncPending, doc_sync_warning: docSyncSummary(reqNow) }
          : {}),
        ...blockerBlock,
        note: finishNote,
      }
    }
