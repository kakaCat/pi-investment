/**
 * Decompose 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineDecomposeTool / reqboard_decompose 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/Decompose
 */
import type { UseCaseDeps } from '../ports.js'
import {
  asScope,
  assertDagAcyclic,
  normalizePlanTasks,
  normalizeText,
  planApproved,
  recordStatus,
  type PlanTask,
  type TaskRecord,
} from '../../shared/protocol.js'
import { checkDecomposeIdempotency } from '../../domain/workflow/DecomposeSpec.js'
import { clearDocSync } from '../../domain/workflow/DocSyncSpec.js'
import { openRequirementsFor } from '../internal/window.js'
import { fmt } from '../../domain/text/fmt.js'
import { describeConflicts, findWorkSurfaceConflicts } from '../internal/conflict-check.js'
import { applyTaskRollup } from '../internal/rollup.js'
import { captureSnapshot } from '../internal/token-usage.js'
import { registerArtifact } from '../internal/artifact-gates.js'
import { syncRequirementMarks } from './SyncRequirementMarks.js'
import { assertClauseCoverageGate, requirementRefsOf } from '../internal/content-gate-wiring.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
} from '../internal/support.js'

export async function executeDecompose(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; tasks?: unknown }
      if (a.tasks !== undefined && (!Array.isArray(a.tasks) || a.tasks.length === 0)) {
        reject('reqboard_decompose 未执行：tasks 传了就必须是非空数组（不传 = 直接落库已批准的计划）', 'REQBOARD_INVALID_INPUT')
      }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) {
        reject('reqboard_decompose 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      }
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (target === undefined) {
        reject(
          'reqboard_decompose 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求（只能拆自己的需求）',
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }
      if (target.status === 'draft') {
        reject('reqboard_decompose 未执行：需求还在立项态，先 reqboard_move 到 brainstorming（方案确认后）再拆', 'REQBOARD_BAD_STATUS')
      }
      if (target.status === 'done' || target.status === 'archived' || target.status === 'canceled') {
        reject('reqboard_decompose 未执行：需求已处于 ' + target.status + '，不能再拆分', 'REQBOARD_BAD_STATUS')
      }
      // ── 幂等守卫（REQ-2e9473 t01）────────────────────────────────────────
      // 事故 B（REQ-6f39b5）：拆分成功落库后同程序内 move 被闸门拒绝 → agent 不知已拆
      // 成功，重试 decompose → 幽灵任务双倍落库、rollup 永久卡死。两道防线：
      //  ① 状态已**越过**拆分（实施/验收中）→ 说明已拆过，拒绝；
      //  ② 台账已有该需求的未取消任务 → 拒绝并返回已有清单（防状态异常时的漏网）。
      // 2026-09-17 修正（本需求自身实测触发）：原守卫把 decomposing 也当作"已拆过"，但计划
      // 批准（reqboard_ask_confirm target=plan）会**自动**把 design → decomposing，于是正常
      // 路径必然先到 decomposing 再调 decompose → 被自己的守卫拒死，审批流水线自锁。
      // 正解：幽灵任务的唯一判据是"已有任务"（防线②），状态只用于区分"是否已越过拆分"。
      // 两道防线的判定在 domain/workflow/DecomposeSpec.ts（REQ-47939a t3）。
      const existingTasks = snapshot.tasks.filter(t => t.requirementId === target.id && t.status !== 'canceled')
      const idempotency = checkDecomposeIdempotency(target.status, existingTasks)
      if (!idempotency.ok) {
        reject('reqboard_decompose 未执行：' + idempotency.reason, idempotency.code)
      }

      // ── 计划闸门（plan mode 的代码级 HARD GATE）──────────────────────────
      // 拆分不是自由创作：落库的必须是**人已经批准过**的那张任务表。没有计划或计划未
      // 批准 → 直接拒绝（agent 无法自行越过；人批准是唯一钥匙）。
      if (!planApproved(target)) {
        reject(
          'reqboard_decompose 未执行：该需求还没有已批准的拆分计划。'
          + '拆分计划属拆分阶段（2026-09-21 用户裁定）：先 reqboard_submit(kind=plan) 提交拆分计划'
          + '（decomposition.md + 摘要 + 任务表），请人在项目看板点「批准计划」（或弹框批准），批准后才能拆分落库',
          'REQBOARD_PLAN_NOT_APPROVED',
        )
      }
      const planTasks: PlanTask[] = target.plan?.tasks ?? []
      // ── W7 阶段产物边界（REQ-2e9473 t17）：两条路径 ─────────────────────
      //  路径 A（创作型，W7 新语义）：计划只含设计（tasks 空）→ decompose 承担任务卡
      //   创作，必须显式传 tasks；任务卡质量（implementation/可证伪 acceptance）由
      //   normalizePlanTasks 强制，人工把关在「拆分确认门」（decomposing→implementing）。
      //  路径 B（计划携带任务表，兼容旧流程）：落库以批准的计划为准；显式传 tasks 时
      //   key 集合必须一致（防「批了 A、落库 B」）。
      let draft: Array<{
        key: string; title: string; description: string; phase: string; side: string
        acceptance: string; implementation: string; context: string; dependsOn: string[]
      }>
      if (planTasks.length === 0) {
        if (a.tasks === undefined || !Array.isArray(a.tasks) || a.tasks.length === 0) {
          reject(
            'reqboard_decompose 未执行：设计未含任务表（W7 新语义）——请传入 tasks 创作任务卡'
            + '（每张卡必须含 implementation 与可证伪 acceptance；decompose 即任务卡创作口）',
            'REQBOARD_TASKS_REQUIRED',
          )
        }
        const creative = normalizePlanTasks(a.tasks)
        draft = creative.map(t => ({
          key: t.key,
          title: t.title,
          description: t.description ?? '',
          phase: t.phase ?? 'implement',
          side: t.side ?? 'fullstack',
          acceptance: t.acceptance ?? '',
          implementation: t.implementation ?? '',
          context: '',
          dependsOn: [...(t.dependsOn ?? [])],
        }))
      } else {
        // 显式传 tasks 时，key 集合必须与批准的计划一致——防止「批了 A、落库 B」
        if (a.tasks !== undefined) {
          const givenKeys = new Set(
            (a.tasks as unknown[]).map((raw, i) => {
              const o = (typeof raw === 'object' && raw !== null ? raw : {}) as Record<string, unknown>
              return normalizeText(o.key, 'tasks[].key', 40) || 'k' + (i + 1)
            }),
          )
          const planKeys = new Set(planTasks.map(t => t.key))
          const same = givenKeys.size === planKeys.size && [...givenKeys].every(k => planKeys.has(k))
          if (!same) {
            reject(
              'reqboard_decompose 未执行：传入的任务表与已批准计划不一致（批准的是 '
              + [...planKeys].join(', ') + '）。要改拆分方案请重新 reqboard_plan_submit 并让人重新批准',
              'REQBOARD_PLAN_MISMATCH',
            )
          }
        }
        // 落库内容以批准的计划为准
        draft = planTasks.map(t => ({
          key: t.key,
          title: t.title,
          description: t.description ?? '',
          phase: t.phase ?? 'implement',
          side: t.side ?? 'fullstack',
          acceptance: t.acceptance ?? '',
          implementation: t.implementation ?? '',
          context: '',
          dependsOn: [...(t.dependsOn ?? [])],
        }))
      }
      // 薄卡检测（REQ-2e9473 t04）：新计划在 plan_submit 已被强制要求 implementation（t03），
      // 这里拦的是"规则生效前已被人工批准的历史计划"——人看过这张薄卡并批了，硬拒会锁死
      // 存量需求（REQ-2e9473 自身即是），故不硬拦、返回 thin_cards 警告提示补实施卡。
      const thinCards = draft.filter(d => d.implementation.length === 0).map(d => d.key + ' ' + d.title)

      // ── 冲突拦截（REQ-4842fe t9/FR-10 主防线）────────────────────────────
      // 互无依赖的父卡若声明同一文件，并行跑会互相覆盖 → 拆分阶段即拒（比运行期事后发现便宜）。
      const conflicts = findWorkSurfaceConflicts(draft)
      if (conflicts.length > 0) {
        reject(fmt('reqboard_decompose 未执行：互无依赖的任务卡声明了同一文件（并行会互相覆盖）——{list}。请重划范围或建立依赖', { list: describeConflicts(conflicts) }), 'REQBOARD_FILE_CONFLICT')
      }

      // ── 覆盖门禁（REQ-d3e61a T-3 / FR-1）：需求里每条根编号必须有落点 ──────────
      // 落点 = 被某张任务卡用 requirement_refs 接收，或在该条款旁显式标「本轮不做」。
      // 拦的是"无记录"，不是"不许多做少做"（这正是 R9 静默丢失的堵口）。
      // 刻意放在 mutate 之前：拒绝时不留任何副作用。
      // 任务↔需求编号的绑定**不落库**（TaskRecord 无该字段），故随 decomposition.md 的 RTM
      // 覆盖表持久化——它本就是规范里的 RTM 核心，且不必改被占用的 protocol.ts。
      const rawTaskInputs = [
        ...((a.tasks as unknown[] | undefined) ?? []),
        ...(planTasks as readonly unknown[]),
      ]
      // 取**并集**：同一 key 可能同时出现在显式 tasks 与已批准计划里，后写不能覆盖前写的 refs
      // （否则"计划携带任务表"这条常见路径上，RTM 表会恒显示"未声明接收任何条款"——E2E 实测踩过）。
      const refsByKey = new Map<string, string[]>()
      for (const raw of rawTaskInputs) {
        const o = (typeof raw === 'object' && raw !== null ? raw : {}) as Record<string, unknown>
        if (typeof o.key !== 'string' || o.key.length === 0) continue
        const merged = new Set([...(refsByKey.get(o.key) ?? []), ...requirementRefsOf(raw)])
        refsByKey.set(o.key, [...merged])
      }
      const coverageFailure = await assertClauseCoverageGate(deps.docs, target, rawTaskInputs)
      if (coverageFailure !== undefined) {
        reject(coverageFailure.message, coverageFailure.code)
      }

      const nowTs = deps.clock.now()
      const reqDir = 'docs/requirements/' + target.id
      try {
        const result = await deps.repo.mutate('task-created', (ledger) => {
          const req = ledger.requirements.find(r => r.id === target.id)
          if (req === undefined) return undefined
          const used = new Set(ledger.tasks.map(t => t.id))
          const idByKey = new Map<string, string>()
          const records: TaskRecord[] = []
          const commentLines: string[] = []
          for (const d of draft) {
            let id = deps.ids.task()
            for (let guard = 0; guard < 50 && used.has(id); guard++) id = deps.ids.task()
            used.add(id)
            idByKey.set(d.key, id)
            const record: TaskRecord = {
              id,
              requirementId: req.id,
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
          assertDagAcyclic([...ledger.tasks, ...records], req.id)
          ledger.tasks.push(...records)
          // 销标（REQ-2e9473 t19/W8）：拆分重做即完成 decomposition 同步（规则在 DocSyncSpec.ts，t3）
          clearDocSync(req, 'decomposition')
          for (const r of records) {
            const deps = r.dependsOn.length > 0 ? '（依赖 ' + r.dependsOn.join(', ') + '）' : ''
            commentLines.push('- ' + r.id + ' ' + r.title + deps)
          }
          req.comments.push({
            id: deps.ids.comment(),
            body:
              '[拆分] 按已批准的拆分计划落库 ' + records.length + ' 个任务'
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
            { now: nowTs, commentId: () => deps.ids.comment(), snapshot: () => captureSnapshot(deps, windowKey) },
            req.id,
          )
          return { tasks: records, requirements: [req, ...advanced] }
        })
        const req = (result.changed.requirements ?? [])[0]
        const created = (result.changed.tasks ?? []).map((t, i) => ({
          key: draft[i]?.key ?? '',
          id: t.id,
          title: t.title,
          depends_on: [...t.dependsOn],
        }))
        // 调用 DSH todo_write 工具，注册任务到 DSH 任务系统（REQ-327bdf t-f0e869）。
        // 为什么放在 mutate **之后**：repo.mutate 的回调是同步契约（返回 LedgerChange），
        // 在里面 await 会让整个模块无法被 esbuild/vite 解析（实测：31 个测试文件连模块都加载不了）。
        // 可用性守卫：exec.tools 只在真实 DSH 会话里存在，测试夹具与直连调用没有它——
        // 注册 todo 是附加动作，不该让"没这个工具"变成 decompose 失败。
        const tools = (exec as { tools?: { todo_write?: (a: unknown) => Promise<unknown> } } | undefined)?.tools
        if (tools?.todo_write !== undefined && created.length > 0) {
          await tools.todo_write({
            todos: created.map(c => ({ content: c.id + ': ' + c.title, status: 'pending' })),
          })
        }
        // ── 产物登记（REQ-31e11f t4）：decomposition + 每任务 task_detail ──
        const decompPath = reqDir + '/decomposition.md'
        // 生成 decomposition.md（计划任务表 ↔ 落库任务 id 对照）
        const decompContent = [
          '# ' + target.id + ' 拆分清单（decomposition）',
          '',
          '> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照',
          '',
          '## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）',
          '',
          '| 根编号 | 计划 key | 任务 id | 标题 | 状态 |',
          '|--------|---------|--------|------|------|',
          ...created.flatMap(c => {
            const t = (result.changed.tasks ?? []).find(x => x.id === c.id)!
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
            const t = (result.changed.tasks ?? []).find(x => x.id === c.id)!
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
          const t = (result.changed.tasks ?? []).find(x => x.id === c.id)!
          const taskPath = reqDir + '/tasks/' + c.id + '.md'
          if (!docs.exists(taskPath)) {
            const depTitles = c.depends_on.map(depId => {
              const dep = (result.changed.tasks ?? []).find(x => x.id === depId)
              return dep ? dep.title : depId
            })
            // 三要素节（在做什么 / 解决什么问题 / 得到什么结果）是**契约**，不是排版：
            // REQ-640a55 的三要素门禁按标题行定位这三节，缺任一或正文为空都会被 task_card_incomplete 拦下。
            // 改名请同步 AmendTaskAcceptance 的段定位正则（它按「## 得到什么结果」找段做整段替换）。
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
        // 需求文档同步逐条接收状态（T-5 / FR-3）：拆分那次就把「谁接了哪条」落到文档上，
        // 而不是等第一张卡动起来才出现。回写失败不阻断拆分（文档是留痕面）。
        try {
          const snap = deps.repo.snapshot()
          const r0 = snap.requirements.find(x => x.id === target.id)
          if (r0 !== undefined) await syncRequirementMarks(deps, r0, snap.tasks)
        } catch {
          /* 回写失败不阻断拆分 */
        }
        // 登记产物
        await deps.repo.mutate('requirement-updated', (ledger) => {
          const r = ledger.requirements.find(x => x.id === target.id)
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
          return { requirements: [r] }
        })
        return {
          success: true,
          requirement_id: target.id,
          requirement_status: req?.status ?? target.status,
          created,
          ...(thinCards.length > 0
            ? {
                thin_cards: thinCards,
                warning: '⚠️ ' + thinCards.length + ' 张薄卡缺实施方案（历史批准计划）：' + thinCards.join('；')
                  + '。开工前请先在任务卡补齐「实施方案」段（新计划在 plan_submit 已强制要求）',
              }
            : {}),
          note: '已落库 ' + created.length + ' 个任务。拆分计划已获批准（decomposition 产物已落章）——需求可推进到 implementing（reqboard_move；经批准弹框路径会自动推进）；任务开工/完成用 reqboard_task_move（任务全部完成后需求自动进入验收）',
        }
      } catch (err) {
        const code = (err as { code?: string }).code ?? 'REQBOARD_INVALID_INPUT'
        reject('reqboard_decompose 未执行：' + ((err as Error).message ?? String(err)), code)
      }
    }