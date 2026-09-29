/**
 * Decompose 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineDecomposeTool / reqboard_decompose 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/Decompose
 */
import type { UseCaseDeps } from '../ports.js'
import {
  normalizePlanTasks,
  normalizeText,
  planApproved,
  type PlanTask,
} from '../../shared/protocol.js'
import { checkDecomposeIdempotency } from '../../domain/workflow/DecomposeSpec.js'
import { openRequirementsFor } from '../internal/window.js'
import { fmt } from '../../domain/text/fmt.js'
import { describeConflicts, findWorkSurfaceConflicts } from '../internal/conflict-check.js'
import { assertClauseCoverageGate, requirementRefsOf } from '../internal/content-gate-wiring.js'
import { reject, agentIdFromExec, requireLiveDriver } from '../internal/support.js'
import { landPlanTasks, type PlanTaskDraft } from '../internal/plan-landing.js'
import { queueRelativePath } from '../../domain/queue/queuePath.js'
import { taskStoreOf } from './queue-access.js'

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
      
      // ── REQ-260925212722-96e7 FR-8：Dive armed 检查 ──────────────────────
      // Dive 模式 armed 时，禁止手动调用拆分工具（自动流程接管）
      if (target.dive?.activation === 'armed') {
        reject(
          'reqboard_decompose 未执行：需求 ' + target.id + ' 的 Dive 自动流程已启用，不允许手动拆分。若需手动操作，请先调用 reqboard_clear_pause() 解除锁定。',
          'REQBOARD_DIVE_ARMED'
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
      // 任务已迁出台账（v9）：幂等守卫的"已有任务"判据改读队列。
      const existingTasks = (await taskStoreOf(deps).listByRequirement(target.id)).filter(t => t.status !== 'canceled')
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
      let draft: PlanTaskDraft[]
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
          // 子卡段控制（REQ-260928185112-e20d）：两条路径（创作型 tasks / 计划携带任务表）都要透传，
          // 否则拆分节点写了 stages/skipIntegration，落库时照样丢。
          ...(t.stages !== undefined ? { stages: [...t.stages] } : {}),
          ...(t.skipIntegration === true ? { skipIntegration: true } : {}),
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
          // 子卡段控制（REQ-260928185112-e20d）：两条路径（创作型 tasks / 计划携带任务表）都要透传，
          // 否则拆分节点写了 stages/skipIntegration，落库时照样丢。
          ...(t.stages !== undefined ? { stages: [...t.stages] } : {}),
          ...(t.skipIntegration === true ? { skipIntegration: true } : {}),
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
      try {
        const tools = (exec as { tools?: { todo_write?: (a: unknown) => Promise<unknown> } } | undefined)?.tools
        const landed = await landPlanTasks(deps, {
          requirementId: target.id,
          windowKey,
          nowTs,
          draft,
          refsByKey,
          tools,
        })
        const created = landed.created
        const rtmData = landed.rtm
        // t11（REQ-260927202051-f6df FR-1）：拆分后任务落在哪份队列文件——返回体必须给出**非空**
        // `queue_file`，否则调用方无从得知"台账没长东西，那卡去哪了"。
        // 路径口径的**单一事实源在 domain**（`domain/queue/queuePath.ts`，零 import，application 可直接用）；
        // 基础设施层的 `QueueRepository.queueRelativePath` 只是它的再导出，两份实现复活即契约测试红。
        const queueFile = queueRelativePath(target.id)
        return {
          success: true,
          requirement_id: target.id,
          requirement_status: landed.requirement?.status ?? target.status,
          queue_file: queueFile,
          tasks_created: landed.createdIds.length,
          created,
          ...(rtmData !== undefined
            ? {
                task_coverage: rtmData.task_coverage,
                coverage_check: rtmData.coverage_check,
                ...(rtmData.coverage_check.unreceived_clauses.length > 0
                  ? { warning: '⚠️ 部分 FR 未被任务覆盖：' + rtmData.coverage_check.unreceived_clauses.join(', ') + '（覆盖率 ' + rtmData.coverage_check.coverage_rate + '%）' }
                  : {}),
              }
            : {}),
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