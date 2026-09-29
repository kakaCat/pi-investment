/**
 * 计划任务落库编排（REQ-260927100007-b8ba t4 / FR-1）——「把已批准计划的任务表写成任务卡」
 * 的**唯一实现**。
 *
 * 为什么要抽出来：同一段落库编排原先只存在于 reqboard_decompose 用例里，而「批准拆分计划」这条
 * **更常见**的入口却被改成"只推进状态、把落库委托给 Dive 续跑"（confirm-settle 里 createdCount=0）。
 * 实测后果：批准后台账 0 任务、看板拆分节点 DAG 空白、实施覆盖度为 0，且零告警静默数日。
 * 抽成本模块后，两条入口共用同一份落库编排——批准即可同步落库，落库失败则响亮地失败。
 *
 * 职责边界：本模块只做「计划任务表 → 任务卡 DAG（含任务卡文档 / decomposition.md / 产物登记 /
 * RTM 覆盖度）」。计划是否已批准、条款覆盖门禁、薄卡检测等**准入判定**留在调用方。
 *
 * REQ-260927202051-f6df t11（FR-1）：任务不再写台账（v9 无 `tasks` 键），改为
 * **① 先 `taskStore.createMany` 写 queue.json → ② 后 `repo.mutate` 写需求侧**。
 * 两条调用路径（`Decompose.ts:189` 与 `confirm-settle.ts:276`）共用本函数，故都自动覆盖；
 * 幂等由 `createMany`（已存在 id 跳过、不写盘）保证——重复拆分不会改写已执行中的卡，
 * 且第二次调用的 queue.json mtime 不变（t11 的幂等判据）。
 *
 * @module dsh-pmboard/application/internal/plan-landing
 */
import type { UseCaseDeps } from '../ports.js'
import {
  asScope,
  assertDagAcyclic,
  recordStatus,
  type RequirementRecord,
  type TaskRecord,
} from '../../shared/protocol.js'
import { clearDocSync } from '../../domain/workflow/DocSyncSpec.js'
import type { StageKind } from '../../domain/task/SubtaskTemplate.js'
import { applyTaskRollup } from './rollup.js'
import { captureSnapshot } from './token-usage.js'
import { registerArtifact } from './artifact-gates.js'
import { stampCheckpoint } from './interruption.js'
import { syncRequirementMarks } from '../use-cases/SyncRequirementMarks.js'
import { taskStoreOf } from '../use-cases/queue-access.js'
import { generateRTMData } from './rtm-integration.js'

/** 待落库的任务草稿（来自已批准计划或显式 tasks 创作）。 */
export interface PlanTaskDraft {
  key: string
  title: string
  description: string
  phase: string
  side: string
  acceptance: string
  implementation: string
  context: string
  dependsOn: string[]
  /**
   * 子卡段逃生舱口（REQ-260928185112-e20d）：显式覆盖"这张卡落哪几段"。
   * 此前协议层收下了 stages，但**没有经本结构传到 TaskRecord**，于是拆分节点写了也不生效。
   */
  stages?: StageKind[]
  /** 本卡无接口可联调 → 不落联调子卡（与 TaskRecord.skipIntegration 同语义）。 */
  skipIntegration?: boolean
}

/** 落库后的轻量投影（工具返回体用）。 */
export interface LandedTaskRef {
  key: string
  id: string
  title: string
  depends_on: string[]
}

export interface LandPlanTasksInput {
  requirementId: string
  windowKey: string
  nowTs: number
  draft: PlanTaskDraft[]
  /** 计划 key → 需求条款编号（写进 TaskRecord.requirementRefs 并生成 RTM 覆盖表）。 */
  refsByKey: Map<string, string[]>
  /** DSH todo_write（真实会话才有；测试/直连调用没有 → 跳过）。 */
  tools?: { todo_write?: (a: unknown) => Promise<unknown> } | undefined
}

export interface LandPlanTasksResult {
  created: LandedTaskRef[]
  requirement: RequirementRecord | undefined
  /**
   * 本次**真正新增**的任务 id（幂等跳过的不计）。
   * t11 判据：重复调用时本数组为空 + queue.json mtime 不变。
   */
  createdIds: string[]
  rtm?: Awaited<ReturnType<typeof generateRTMData>>
}

/**
 * 把任务草稿写进队列（+ 生成任务卡文档 / decomposition.md / 登记产物 / 刷新需求接收标记 / RTM）。
 * 任一步抛错即向上抛——调用方据此决定「不推进 + 响亮地失败」。
 */
export async function landPlanTasks(deps: UseCaseDeps, input: LandPlanTasksInput): Promise<LandPlanTasksResult> {
  const { requirementId, windowKey, nowTs, draft, refsByKey } = input
  const store = taskStoreOf(deps)

  const req0 = deps.repo.snapshot().requirements.find(r => r.id === requirementId)
  if (req0 === undefined) {
    return { created: [], requirement: undefined, createdIds: [] }
  }

  // 队列既有任务（幂等去重 + 环检测的完整图输入）。
  const existing = await store.listByRequirement(requirementId)
  const used = new Set(existing.map(t => t.id))
  const idByKey = new Map<string, string>()
  const keyById = new Map<string, string>()
  const records: TaskRecord[] = []
  for (const d of draft) {
    let id = deps.ids.task()
    for (let guard = 0; guard < 50 && used.has(id); guard++) id = deps.ids.task()
    used.add(id)
    idByKey.set(d.key, id)
    keyById.set(id, d.key)
    const reqDir = 'docs/requirements/' + requirementId
    const record: TaskRecord = {
      id,
      requirementId,
      title: d.title,
      // cardDoc 随落库写死（REQ-260923134706-e72f 实测断链修复：此前只生成文档+登记产物，
      // 没写这个字段，面板「（无任务卡）」不可点）；读路径另有产物回填兼容存量（QueryStageDetail.withCardDoc）
      cardDoc: reqDir + '/tasks/' + id + '.md',
      description: d.description,
      phase: d.phase as TaskRecord['phase'],
      side: d.side as TaskRecord['side'],
      dependsOn: d.dependsOn.map(dep => idByKey.get(dep) ?? dep),
      scope: asScope({}),
      acceptance: d.acceptance,
      implementation: d.implementation,
      context: d.context,
      // 子卡段控制（REQ-260928185112-e20d）：显式 stages 覆盖默认；无接口的卡可跳过联调段。
      // 不填时落 undefined → 展开时按卡 phase、其次需求分类兜底（resolveSubtaskStages）。
      ...(d.stages !== undefined ? { stages: [...d.stages] } : {}),
      ...(d.skipIntegration === true ? { skipIntegration: true } : {}),
      // 从 refsByKey Map 中获取该任务的 requirement_refs（REQ-260925172227-2d61 RTM 覆盖度追踪）
      requirementRefs: refsByKey.get(d.key) ?? [],
      status: 'todo',
      blocked: false,
      executions: [],
      statusHistory: [],
      comments: [],
      version: 1,
      createdAt: nowTs,
      updatedAt: nowTs,
      createdBy: { kind: 'agent', sessionId: windowKey },
      updatedBy: { kind: 'agent', sessionId: windowKey },
    }
    recordStatus(record, 'todo', nowTs, { kind: 'agent', sessionId: windowKey }, '拆分落库（reqboard_decompose）')
    records.push(record)
  }
  // 环检测的图 = 队列既有 + 本次新增（dependsOn 已在上面解析为真实 id）。
  assertDagAcyclic([...existing, ...records], requirementId)

  // ── ① 任务写（**先**）：queue.json（幂等：已存在 id 跳过；全已存在则不写盘 → mtime 不变）──────
  const createdRaw = await store.createMany(requirementId, records)
  const created: LandedTaskRef[] = createdRaw.map(t => ({
    key: keyById.get(t.id) ?? '',
    id: t.id,
    title: t.title,
    depends_on: [...t.dependsOn],
  }))
  // rollup 的输入任务集 = 队列事实（既有 + 本次新增），在 repo.mutate 之前取好（回调是同步契约）。
  const allTasks = await store.listByRequirement(requirementId)

  // ── ② 需求写（**后**）：评论 / 销标 / rollup —— 不含任何任务字段 ─────────────────────
  const result = await deps.repo.mutate('requirement-updated', (ledger) => {
    const req = ledger.requirements.find(r => r.id === requirementId)
    if (req === undefined) return undefined
    // 销标（REQ-2e9473 t19/W8）：拆分重做即完成 decomposition 同步（规则在 DocSyncSpec.ts）
    clearDocSync(req, 'decomposition')
    const commentLines = createdRaw.map(r => {
      const dep = r.dependsOn.length > 0 ? '（依赖 ' + r.dependsOn.join(', ') + '）' : ''
      return '- ' + r.id + ' ' + r.title + dep
    })
    req.comments.push({
      id: deps.ids.comment(),
      body:
        '[拆分] 按已批准的拆分计划落库 ' + createdRaw.length + ' 个任务'
        + (req.plan !== undefined ? '（计划 ' + req.plan.path + '，批准于 ' + new Date(req.plan.approvedAt ?? 0).toISOString() + '）' : '')
        + '：\n' + commentLines.join('\n')
        + '\n（窗口 ' + windowKey + '）',
      createdAt: nowTs,
      createdBy: { kind: 'agent', sessionId: windowKey },
    })
    req.version += 1
    req.updatedAt = nowTs
    req.updatedBy = { kind: 'agent', sessionId: windowKey }
    const advanced = applyTaskRollup(
      ledger,
      allTasks,
      { now: nowTs, commentId: () => deps.ids.comment(), snapshot: () => captureSnapshot(deps, windowKey) },
      req.id,
    )
    return { requirements: [req, ...advanced] }
  })
  const req = (result.changed.requirements ?? [])[0]

  // 调用 DSH todo_write 工具，注册任务到 DSH 任务系统（REQ-327bdf t-f0e869）。
  // 为什么放在 mutate **之后**：repo.mutate 的回调是同步契约（返回 LedgerChange），在里面 await
  // 会让整个模块无法被 esbuild/vite 解析。可用性守卫：exec.tools 只在真实 DSH 会话里存在。
  const tools = input.tools
  if (tools?.todo_write !== undefined && created.length > 0) {
    await tools.todo_write({
      todos: created.map(c => ({ content: c.id + ': ' + c.title, status: 'pending' })),
    })
  }
  // ── 产物登记（REQ-31e11f t4）：decomposition + 每任务 task_detail ──
  const reqDir = 'docs/requirements/' + requirementId
  const decompPath = reqDir + '/decomposition.md'
  // 生成 decomposition.md（计划任务表 ↔ 落库任务 id 对照）
  const decompContent = [
    '# ' + requirementId + ' 拆分清单（decomposition）',
    '',
    '> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照',
    '',
    '## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）',
    '',
    '| 根编号 | 计划 key | 任务 id | 标题 | 状态 |',
    '|--------|---------|--------|------|------|',
    ...created.flatMap(c => {
      const t = createdRaw.find(x => x.id === c.id)!
      const refs = refsByKey.get(c.key) ?? []
      const cells = refs.length > 0 ? refs : ['—（未声明接收任何条款）']
      return cells.map(r => '| ' + r + ' | ' + c.key + ' | ' + c.id + ' | ' + t.title + ' | ' + t.status + ' |')
    }),
    '',
    '## §2 任务清单',
    '',
    '| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |',
    '|---------|--------|------|------|------|------|---------|',
    ...created.map(c => {
      const t = createdRaw.find(x => x.id === c.id)!
      return '| ' + c.key + ' | ' + c.id + ' | ' + t.title + ' | ' + t.phase + ' | ' + t.side + ' | ' + (c.depends_on.join(', ') || '-') + ' | ' + (t.acceptance || '-') + ' |'
    }),
    '',
  ].join('\n')
  const docs = deps.docs
  if (!docs.exists(decompPath)) {
    await docs.write(decompPath, decompContent)
  }
  // 生成每任务自足任务卡骨架
  for (const c of created) {
    const t = createdRaw.find(x => x.id === c.id)!
    const taskPath = reqDir + '/tasks/' + c.id + '.md'
    if (!docs.exists(taskPath)) {
      const depTitles = c.depends_on.map(depId => {
        const dep = createdRaw.find(x => x.id === depId)
        return dep ? dep.title : depId
      })
      // 三要素节（在做什么 / 解决什么问题 / 得到什么结果）是**契约**，不是排版：
      // REQ-640a55 的三要素门禁按标题行定位这三节，缺任一或正文为空都会被 task_card_incomplete 拦下。
      const taskContent = [
        '# ' + c.id + ' ' + t.title,
        '',
        '> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件',
        '',
        '## 在做什么',
        t.title,
        '',
        '## 解决什么问题',
        t.context || '（未填写——开工前补充这张卡要解决的业务问题）',
        '',
        '## 范围',
        '- 阶段：' + t.phase,
        '- 端侧：' + t.side,
        ...(t.scope && (t.scope.apis.length > 0 || t.scope.tables.length > 0 || t.scope.files.length > 0)
          ? ['- APIs：' + t.scope.apis.join('、'), '- 表：' + t.scope.tables.join('、'), '- 文件：' + t.scope.files.join('、')]
          : []),
        '',
        '## 得到什么结果',
        t.acceptance || '（未填写）',
        '',
        '## 实施方案（implementation）',
        t.implementation || '（薄卡：未填写——开工前必须先补实施方案）',
        '',
        '## 上游产出摘要（dependsSummary）',
        ...(depTitles.length > 0 ? depTitles.map(d => '- ' + d) : ['- （无依赖）']),
        '',
        '## 执行方式提示（executorHint）',
        '优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史',
        '',
      ].join('\n')
      await docs.write(taskPath, taskContent)
    }
  }
  // 需求文档同步逐条接收状态（T-5 / FR-3）：拆分那次就把「谁接了哪条」落到文档上。
  // 回写失败不阻断拆分（文档是留痕面）。
  try {
    const r0 = deps.repo.snapshot().requirements.find(x => x.id === requirementId)
    if (r0 !== undefined) await syncRequirementMarks(deps, r0, allTasks)
  } catch {
    /* 回写失败不阻断拆分 */
  }
  // 登记产物
  await deps.repo.mutate('requirement-updated', (ledger) => {
    const r = ledger.requirements.find(x => x.id === requirementId)
    if (r === undefined) return undefined
    registerArtifact(r, {
      stage: 'decomposing', kind: 'decomposition', path: decompPath,
      registeredAt: nowTs, registeredBy: { kind: 'agent', sessionId: windowKey },
    })
    for (const c of created) {
      registerArtifact(r, {
        stage: 'implementing', kind: 'task_detail', path: reqDir + '/tasks/' + c.id + '.md',
        registeredAt: nowTs, registeredBy: { kind: 'agent', sessionId: windowKey },
      })
    }
    stampCheckpoint(r, nowTs, 'reqboard_decompose'); return { requirements: [r] }
  })
  // RTM 集成：生成 task_coverage 和覆盖度统计（REQ-260925172227-2d61 FR-1）。
  // 生成失败不阻断拆分，只记警告（RTM 是留痕面）。
  let rtm: Awaited<ReturnType<typeof generateRTMData>> | undefined
  try {
    rtm = await generateRTMData(reqDir, created as unknown as Parameters<typeof generateRTMData>[1])
  } catch (rtmErr) {
    console.warn('[plan-landing] RTM 集成失败:', rtmErr)
  }
  return {
    created,
    requirement: req,
    createdIds: created.map(c => c.id),
    ...(rtm !== undefined ? { rtm } : {}),
  }
}
