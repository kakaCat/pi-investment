/**
 * L2 用例测试（REQ-47939a t6）：12 个用例 + 3 个查询投影，全部用内存端口（不落盘）。
 *
 * 断言口径：用例编排（前置/后置/幂等/跨聚合一致性）+ 与搬迁前逐字一致的拒绝码与消息。
 */
import { describe, it, expect } from 'vitest'
import { makeHarness, req, task } from './harness.js'
import { executeCreateRequirement } from '../../src/application/use-cases/CreateRequirement.js'
import { executeMoveRequirement } from '../../src/application/use-cases/MoveRequirement.js'
import { executeDecompose } from '../../src/application/use-cases/Decompose.js'
import { executeMoveTask } from '../../src/application/use-cases/MoveTask.js'
import { executeReportTask } from '../../src/application/use-cases/ReportTask.js'
import { submitRequirementArtifact, submitPlanArtifact } from '../../src/application/use-cases/SubmitArtifact.js'
import { submitVerification } from '../../src/application/use-cases/SubmitVerification.js'
import { submitArchive } from '../../src/application/use-cases/SubmitArchive.js'
import { confirmArtifact } from '../../src/application/use-cases/ConfirmArtifact.js'
import { askConfirm } from '../../src/application/use-cases/AskConfirm.js'
import { acceptSheet } from '../../src/application/use-cases/AcceptSheet.js'
import { queryState } from '../../src/application/query/QueryState.js'
import { queryStageDetail } from '../../src/application/query/QueryStageDetail.js'
import { queryStageOverview } from '../../src/application/query/QueryStageOverview.js'
import type { PlanRecord } from '../../src/shared/protocol.js'

const EXEC = { agent: { id: 'session-w-001' } }

describe('t6 · CreateRequirement / QueryState', () => {
  it('创建即立项：draft + sourceSessionId + 首条评论；重复立项被幂等拒绝', async () => {
    const h = makeHarness()
    const out: any = await executeCreateRequirement(h.deps, { title: '新需求', category: 'feature', summary: '摘要' }, EXEC)
    expect(out.success).toBe(true)
    expect(h.repo.ledger.requirements).toHaveLength(1)
    expect(h.repo.ledger.requirements[0]!.status).toBe('draft')
    expect(h.repo.ledger.requirements[0]!.sourceSessionId).toBe('session-w-001')
    await expect(executeCreateRequirement(h.deps, { title: '再来', category: 'bug' }, EXEC))
      .rejects.toMatchObject({ code: 'REQBOARD_WINDOW_BOUND' })
  })

  it('QueryState：bound/open_count/next_actions 与 domain agentNextActions 同源', async () => {
    const h = makeHarness({ requirements: [req({ status: 'design' })] })
    const out: any = await queryState(h.deps, {}, EXEC)
    expect(out.bound).toBe(true)
    expect(out.open_count).toBe(1)
    expect(out.open_requirements[0].id).toBe('REQ-000001')
    expect(Array.isArray(out.next_actions)).toBe(true)
  })
})

describe('t6 · MoveRequirement', () => {
  it('draft → brainstorming 合法推进（agent）；brainstorming → design 是人工闸门', async () => {
    const h = makeHarness({ requirements: [req({ status: 'draft' })] })
    const out: any = await executeMoveRequirement(h.deps, { to: 'brainstorming', reason: '方案' }, EXEC)
    expect(out.success).toBe(true)
    expect(h.repo.ledger.requirements[0]!.status).toBe('brainstorming')

    await expect(executeMoveRequirement(h.deps, { to: 'design' }, EXEC))
      .rejects.toMatchObject({ code: 'REQBOARD_HUMAN_GATE' })
  })
})

describe('t6 · SubmitArtifact（requirement / plan）', () => {
  it('requirement_submit：文档存在 → 登记 requirement 产物（幂等 registered）', async () => {
    const h = makeHarness({ requirements: [req({ status: 'brainstorming' })] })
    h.docs.put('docs/requirements/REQ-000001/requirement.md')
    const out: any = await submitRequirementArtifact(h.deps, {
      path: 'docs/requirements/REQ-000001/requirement.md', summary: '需求文档',
    }, EXEC)
    expect(out.success).toBe(true)
    expect(out.artifact).toEqual({ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-000001/requirement.md' })
    expect(out.registered).toBe(true)
    expect(h.repo.ledger.requirements[0]!.artifacts).toHaveLength(1)
  })

  it('requirement_submit：文档不存在 → REQBOARD_FILE_MISSING', async () => {
    const h = makeHarness({ requirements: [req({ status: 'brainstorming' })] })
    await expect(submitRequirementArtifact(h.deps, { path: 'docs/nope.md' }, EXEC))
      .rejects.toMatchObject({ code: 'REQBOARD_FILE_MISSING' })
  })

  it('plan_submit：decomposing 阶段提交拆分计划 → pending_approval + 登记 decomposition 产物（2026-09-21 裁定）', async () => {
    const h = makeHarness({ requirements: [req({ status: 'decomposing' })] })
    // REQ-2d1c74 FR-5：plan path 存在性补齐——假 docs 也要落桩
    h.docs.put('docs/requirements/REQ-000001/decomposition.md')
    const out: any = await submitPlanArtifact(h.deps, {
      path: 'docs/requirements/REQ-000001/decomposition.md', summary: '计划',
    }, EXEC)
    expect(out.success).toBe(true)
    expect(out.plan_status).toBe('pending_approval')
    expect(h.repo.ledger.requirements[0]!.plan?.path).toBe('docs/requirements/REQ-000001/decomposition.md')
    // 拆分计划归拆分阶段：design 阶段提交被拒
    const h2 = makeHarness({ requirements: [req({ status: 'design' })] })
    await expect(submitPlanArtifact(h2.deps, { path: 'p.md', summary: 's' }, EXEC))
      .rejects.toMatchObject({ code: 'REQBOARD_BAD_STATUS' })
  })
})

describe('t6 · ConfirmArtifact / AskConfirm', () => {
  it('confirm_artifact：缺 evidence 直接拒绝；有 evidence 且核验通道未注入 → 放行', async () => {
    const seedArtifact = { stage: 'brainstorming' as const, kind: 'requirement' as const, path: 'docs/requirements/REQ-000001/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' as const } }
    const h = makeHarness({ requirements: [req({ status: 'brainstorming', artifacts: [seedArtifact] })] })
    await expect(confirmArtifact(h.deps, { target: 'artifact', kind: 'requirement', evidence: '' }, EXEC))
      .rejects.toMatchObject({ code: 'REQBOARD_INVALID_INPUT' })
    const out: any = await confirmArtifact(h.deps, { target: 'artifact', kind: 'requirement', evidence: '用户说可以' }, EXEC)
    expect(out.success).toBe(true)
    expect(out.via).toBe('session')
    expect(h.repo.ledger.requirements[0]!.artifacts![0]!.confirmedAt).toBe(h.clock.t)
  })

  it('confirm_artifact：核验通道可用但未命中 → REQBOARD_EVIDENCE_FAKE', async () => {
    const seedArtifact = { stage: 'brainstorming' as const, kind: 'requirement' as const, path: 'p', registeredAt: 1, registeredBy: { kind: 'agent' as const } }
    const h = makeHarness({ requirements: [req({ status: 'brainstorming', artifacts: [seedArtifact] })] })
    h.session.recentMatch = { ok: false, reason: '没有该窗口的真实用户消息记录' }
    await expect(confirmArtifact(h.deps, { target: 'artifact', kind: 'requirement', evidence: '编造的' }, EXEC))
      .rejects.toMatchObject({ code: 'REQBOARD_EVIDENCE_FAKE' })
  })

  it('ask_confirm：弹框不可用 → fallback=board；肯定项 → 落章 + 自动推进', async () => {
    const seedArtifact = { stage: 'brainstorming' as const, kind: 'requirement' as const, path: 'p', registeredAt: 1, registeredBy: { kind: 'agent' as const } }
    const h = makeHarness({ requirements: [req({ status: 'brainstorming', artifacts: [seedArtifact] })] })
    h.questions.availableFlag = false
    const fb: any = await askConfirm(h.deps, { target: 'artifact', kind: 'requirement', question: '确认？' }, EXEC)
    expect(fb.fallback).toBe('board')

    h.questions.availableFlag = true
    h.questions.answers = [{ id: 'confirm', selected: ['好'] }]
    const out: any = await askConfirm(h.deps, { target: 'artifact', kind: 'requirement', question: '确认？', options: ['好', '不'] }, EXEC)
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(true)
    expect(h.repo.ledger.requirements[0]!.status).toBe('design')
  })
})

describe('t6 · Decompose', () => {
  const approvedPlan: PlanRecord = {
    path: 'docs/requirements/REQ-000001/plan.md', summary: 's', approvedAt: 1,
    submittedAt: 1, submittedBy: { kind: 'agent' as const },
    tasks: [{ key: 't1', title: '做A', description: 'd', phase: 'implement', side: 'backend', dependsOn: [], acceptance: '跑测试看到绿', implementation: '改 a.ts' }],
  }
  it('未批准计划 → REQBOARD_PLAN_NOT_APPROVED', async () => {
    const h = makeHarness({ requirements: [req({ status: 'design', plan: { ...approvedPlan, approvedAt: undefined } })] })
    await expect(executeDecompose(h.deps, {}, EXEC)).rejects.toMatchObject({ code: 'REQBOARD_PLAN_NOT_APPROVED' })
  })

  it('已批准计划 → 落库任务 + 写 decomposition.md / 任务卡 + 登记产物', async () => {
    const h = makeHarness({ requirements: [req({ status: 'design', plan: approvedPlan })] })
    const out: any = await executeDecompose(h.deps, {}, EXEC)
    expect(out.success).toBe(true)
    expect(out.created).toHaveLength(1)
    expect(h.repo.ledger.tasks).toHaveLength(1)
    expect(h.docs.exists('docs/requirements/REQ-000001/decomposition.md')).toBe(true)
    expect(h.docs.exists('docs/requirements/REQ-000001/tasks/' + out.created[0].id + '.md')).toBe(true)
  })

  it('draft 立项态不可拆分 → REQBOARD_BAD_STATUS', async () => {
    const h = makeHarness({ requirements: [req({ status: 'draft' })] })
    await expect(executeDecompose(h.deps, {}, EXEC)).rejects.toMatchObject({ code: 'REQBOARD_BAD_STATUS' })
  })
})

describe('t6 · MoveTask / ReportTask', () => {
  it('task_move→in_progress 返回任务卡全文；cancel 是人工闸门', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'todo' })] })
    const out: any = await executeMoveTask(h.deps, { task_id: 't-000001', to: 'in_progress', reason: '开工' }, EXEC)
    expect(out.success).toBe(true)
    expect(out.task_card.doc_path).toBe('docs/requirements/REQ-000001/tasks/t-000001.md')
    expect(out.task_card.implementation).toBe('改 x.ts')

    await expect(executeMoveTask(h.deps, { task_id: 't-000001', to: 'canceled' }, EXEC))
      .rejects.toMatchObject({ code: 'REQBOARD_HUMAN_GATE' })
  })

  it('task_move→done 无汇报 → done 凭证门拒绝', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'in_review' })] })
    await expect(executeMoveTask(h.deps, { task_id: 't-000001', to: 'done' }, EXEC))
      .rejects.toMatchObject({ code: 'REQBOARD_NO_REPORT' })
  })

  it('task_report：追加任务卡文档并登记 task_detail 产物', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'in_progress' })] })
    const out: any = await executeReportTask(h.deps, {
      task_id: 't-000001', summary: '做完了', completed: ['a'], files_changed: ['packages/x.ts'], next_step: '',
    }, EXEC)
    expect(out.success).toBe(true)
    expect(h.docs.exists('docs/requirements/REQ-000001/tasks/t-000001.md')).toBe(true)
    expect((h.repo.ledger.requirements[0]!.artifacts ?? []).some(a => a.kind === 'task_detail')).toBe(true)
  })
})

describe('t6 · SubmitVerification / SubmitArchive / AcceptSheet', () => {
  it('verify_submit：生成验收单 + 写 verification.md；证据路径不存在 → 拒绝', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'done' })] })
    const out: any = await submitVerification(h.deps, { summary: '交付', evidence: ['npx vitest run 全绿'] }, EXEC)
    expect(out.success).toBe(true)
    expect(out.sheet_version).toBe(1)
    expect(h.docs.exists('docs/requirements/REQ-000001/verification.md')).toBe(true)

    await expect(submitVerification(h.deps, {
      summary: '交付', evidence: ['docs/requirements/REQ-000001/nonexistent.md'],
    }, EXEC)).rejects.toMatchObject({ code: 'REQBOARD_EVIDENCE_MISSING' })
  })

  it('archive_submit：archived 需求备材料成功，目录内未列入清单的文件 → unlisted_files 警告', async () => {
    const h = makeHarness({ requirements: [req({ status: 'archived' })], tasks: [task({ status: 'done' })] })
    h.docs.put('docs/requirements/REQ-000001/notes.md')
    // REQ-2d1c74 FR-5：archive 目录与清单内文档登记前可打开性校验——假 docs 落桩
    h.docs.put('docs/requirements/REQ-000001')
    h.docs.put('docs/requirements/REQ-000001/requirement.md')
    h.docs.put('docs/requirements/REQ-000001/plan.md')
    h.docs.put('docs/requirements/REQ-000001/verification.md')
    const out: any = await submitArchive(h.deps, {
      dir: 'docs/requirements/REQ-000001',
      docs: [
        { kind: 'requirement', path: 'docs/requirements/REQ-000001/requirement.md' },
        { kind: 'plan', path: 'docs/requirements/REQ-000001/plan.md' },
        { kind: 'verification', path: 'docs/requirements/REQ-000001/verification.md' },
      ],
      merged_into: ['docs/architecture/workflow-stages.md'],
      index_entry: '结论',
      manual_updates: [{ path: 'docs/architecture/workflow-stages.md', section: 'x', summary: 'y' }],
    }, EXEC)
    expect(out.success).toBe(true)
    expect(out.status).toBe('archived')
    expect(out.unlisted_files).toContain('docs/requirements/REQ-000001/notes.md')
    void h
  })

  it('archive_submit：非 archived/done → REQBOARD_BAD_STATUS', async () => {
    const h = makeHarness({ requirements: [req({ status: 'design' })] })
    await expect(submitArchive(h.deps, { dir: 'd', docs: [], merged_into: [], index_entry: 'x' }, EXEC))
      .rejects.toMatchObject({ code: 'REQBOARD_BAD_STATUS' })
  })

  it('accept_sheet：无验收单 → REQBOARD_NO_SHEET；弹框不可用 → fallback=board', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'done' })] })
    await expect(acceptSheet(h.deps, {}, EXEC)).rejects.toMatchObject({ code: 'REQBOARD_NO_SHEET' })
    await submitVerification(h.deps, { summary: '交付', evidence: ['npx vitest run 全绿'] }, EXEC)
    h.questions.availableFlag = false
    const out: any = await acceptSheet(h.deps, {}, EXEC)
    expect(out.fallback).toBe('board')
  })
})

// t9 收口（2026-09-17 发起窗口处置）：原 't6 · MigrateLedger（纯变换 + 端口落盘）' 用例块随实现删除。
// 理由：MigrateLedger.ts 是迁移变换的**第二份实现**（src 内零调用），而 t10 的迁移入口是
// scripts/migrate-ledger.ts（D-8）——同一变换两处实现违反 INV-2。保留被端到端实测覆盖的
// 脚本实现（tests/migration.test.ts + 真实副本 dry-run/apply/verify/幂等/回滚），删除未被调用的用例。

describe('t6 · 查询投影', () => {
  it('queryStageDetail / queryStageOverview：只读装配全 8 节点', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'in_progress' })] })
    const detail: any = await queryStageDetail(h.deps, 'REQ-000001', 'implementing')
    expect(detail.stage).toBe('implementing')
    expect(detail.body.tasks).toHaveLength(1)
    const overview: any = await queryStageOverview(h.deps, 'REQ-000001')
    expect(overview.stages.length).toBeGreaterThanOrEqual(7)
    expect(overview.currentStage).toBe('implementing')
  })

  it('queryStageDetail：需求不存在 → not_found', async () => {
    const h = makeHarness()
    await expect(queryStageDetail(h.deps, 'REQ-ffffff', 'draft')).rejects.toMatchObject({ code: 'not_found' })
  })
})
