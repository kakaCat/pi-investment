/**
 * reqboard 模型面工具（用户裁定 · 创建即立项，两问弹框 = 立项门）。
 *
 * 职责：executing-window agent 经两个工具与 reqboard 台账交互——
 *   - reqboard_create：识别到值得立项的新工作后，**先经 ask_user_question 弹「两问
 *     确认」弹框**（问题一需求名称 / 问题二需求类型；选项由对话/消息上下文推导、
 *     最贴切一项置首并标注 (Recommended)、允许自定义输入兜底），**用户作答 = 立项
 *     确认 = 立项门**——本工具按用户确认值**直接创建 REQ**（status='draft'，
 *     sourceSessionId=windowKey 落账 → 窗口随之 bound），无待归类/建议卡中间态，
 *     看板立即可见。
 *   - reqboard_status：只读投影（该窗口 open 需求 + 遗留 pending triage），供
 *     agent 立项前自查，避免已绑定窗口重复立项。
 *
 * 认证（尽力而为，范式承 dsh-tool-goal 但允许服务缺失降级）：
 *   1. identity：exec.agent 必须存在且带 string id（工具由 agent loop 调用才有）。
 *   2. live driver：agents 服务可得时校验
 *      agents.get(id) === agent && agent.status === 'running' &&
 *      agents.currentInitiator() === agent；服务不可得 → 降级为 identity（放行）。
 *   3. direct human（仅 reqboard_create）：agents + sessionProjections 服务都可得时，
 *      要求本 agent 是 root 且当前 open turn 含 source.kind==='user' 的用户消息
 *      （判定逻辑逐字对齐 goal hasDirectHumanInput：从 openTurnStartSeq+1 起扫）；
 *      任一服务不可得 → 降级（无法证伪即放行）。
 * 降级是用户认可的"尽力而为"：root 窗口 + 服务齐全时强制，服务缺失不硬拒。
 *
 * 错误：普通 Error + code 属性（routes bad() 同款 Object.assign）。不 import
 * HarnessError——pmboard 源码物理位于 agent-dh（运行实例 profile node_modules
 * 经 symlink 引用），其 dsh-llm 解析到 agent-dh 自身 pnpm store 副本，与运行实例
 * tools 运行时（profile store 副本）的 HarnessError 非同模块实例，instanceof 判否、
 * code 结构化丢失。因此 message 自带 code 文本（'（CODE）'），模型经工具层读到的是
 * message，语义与 board-tools 现状一致。
 *
 * 直接创建（与 routes /triage/confirm 的 direct-create 分支同形，去掉 triage 中间层）：
 *   actor 按 {kind:'human'} 记账——用户经两问弹框确认立项，语义等同看板人工 confirm；
 *   comment 前缀 '[会话捕获]'（不含 '[LLM 分类]'，不触发 routes legacy 兜底正则；
 *   且新流程根本不产生 triage，正则分支不会被走到）。
 *   幂等：窗口已绑定 open REQ → 拒绝写入（REQBOARD_WINDOW_BOUND）。
 *
 * @module dsh-pmboard/host/agent-tools
 */

import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools';
import { isWindowBound, pendingSuggestionFor, openRequirementsFor } from './capture.js';
import { applyTaskRollup } from './rollup.js';
import type { ReqboardStore } from './store.js';
import type {
  ReqboardLedger,
  RequirementCategory,
  RequirementRecord,
  TriageRecord,
} from '../shared/protocol.js';
import {
  ALL_REQ_CATEGORIES,
  ALL_REQ_STATUSES,
  asReqCategory,
  asReqStatus,
  assertReqTransition,
  newCommentId,
  newRequirementId,
  normalizeText,
  normalizeTitle,
} from '../shared/protocol.js';

/** 结构化认证失败：message 自带（CODE）文本；code 属性仅测试/直接执行消费。 */
function reject(message: string, code: string): never {
  throw Object.assign(new Error(`${message}（${code}）`), { code })
}

/** 工具依赖：store 强依赖；agents/sessionProjections 为惰性服务访问器（缺失 → 认证降级）。 */
export interface ReqboardToolDeps {
  store: ReqboardStore
  now: () => number
  /** 当前 agents 服务（unavailable → undefined）。 */
  agents?: () => unknown
  /** 当前 sessionProjections 服务（unavailable → undefined）。 */
  sessionProjections?: () => unknown
}

/** 结构化读取调用 agent 的 id（identity 层：exec.agent 必须有 string id）。 */
function agentIdFromExec(exec: ToolRunContext): string {
  const raw = (exec.agent as { id?: unknown } | undefined)?.id
  if (typeof raw !== 'string' || raw.length === 0) {
    reject('reqboard 工具需要由执行窗口的 agent 调用（缺 exec.agent）', 'REQBOARD_AGENT_REQUIRED')
  }
  return raw
}

/**
 * 尽力而为的 live-driver 认证：agents 服务可得时要求调用者就是注册表中正在
 * 运行且当前发起回合的同一 agent；服务不可得（测试/降级环境）只做 identity。
 */
function requireLiveDriver(deps: ReqboardToolDeps, exec: ToolRunContext): void {
  const svc = deps.agents?.()
  if (svc === undefined) return
  const agents = svc as {
    get?: (id: string) => unknown
    currentInitiator?: () => unknown
  }
  if (typeof agents.get !== 'function' || typeof agents.currentInitiator !== 'function') return
  const agent = exec.agent
  if (agent === undefined) {
    reject('reqboard 工具需要由执行窗口的 agent 调用（缺 exec.agent）', 'REQBOARD_AGENT_REQUIRED')
  }
  const id = (agent as { id: string }).id
  const live =
    agents.get(id) === agent &&
    (agent as { status?: string }).status === 'running' &&
    agents.currentInitiator() === agent
  if (!live) {
    reject('reqboard_create 需要确切的在线调用 agent 且在其 live driver 回合内', 'REQBOARD_DRIVER_REQUIRED')
  }
}

/**
 * 直接人工回合认证（reqboard_create 用）：agents + sessionProjections 服务都可得时，
 * 要求本 agent 是 root 且当前 open turn 含 source.kind==='user' 的用户消息
 * （从 openTurnStartSeq+1 起扫，逐字对齐 goal hasDirectHumanInput）；任一服务
 * 不可得 → 降级放行（无法证伪即放行）。
 */
function requireDirectHuman(deps: ReqboardToolDeps, exec: ToolRunContext): void {
  const svc = deps.agents?.()
  const projSvc = deps.sessionProjections?.()
  if (svc === undefined || projSvc === undefined) return
  const agents = svc as { roots?: () => unknown[] }
  const projections = projSvc as {
    stateOf?: (session: unknown, kind: string) => { openTurnStartSeq: number | null } | undefined
  }
  if (typeof agents.roots !== 'function' || typeof projections.stateOf !== 'function') return
  const agent = exec.agent
  if (agent === undefined) {
    reject('reqboard 工具需要由执行窗口的 agent 调用（缺 exec.agent）', 'REQBOARD_AGENT_REQUIRED')
  }
  if (!agents.roots().includes(agent)) {
    reject('reqboard_create 需要顶层 agent 窗口的直接人工回合', 'REQBOARD_DIRECT_HUMAN_REQUIRED')
  }
  const session = (agent as { session?: unknown }).session
  const boundary = projections.stateOf(session, 'turnBoundary')
  if (boundary === undefined || boundary.openTurnStartSeq === null) {
    reject('reqboard_create 需要 open 的模型回合（turnBoundary 不可得）', 'REQBOARD_DRIVER_REQUIRED')
  }
  const events = (agent as { session?: { snapshotEvents?: () => unknown[] } }).session?.snapshotEvents?.() ?? []
  for (let seq = boundary.openTurnStartSeq + 1; seq < events.length; seq += 1) {
    const event = events[seq] as { type?: string; data?: { source?: { kind?: string } } } | undefined
    if (event !== undefined && event.type === 'user/message' && event.data?.source?.kind === 'user') return
  }
  reject('reqboard_create 需要本次直接人工回合的用户消息（自主回合禁止立项）', 'REQBOARD_DIRECT_HUMAN_REQUIRED')
}

/** 本窗口最近一条遗留 pending triage（旧流程产物；无则 undefined）。 */
function findPending(ledger: ReqboardLedger, windowKey: string): TriageRecord | undefined {
  return pendingSuggestionFor(ledger, windowKey)
}

/**
 * 直接立项写入：store.mutate('requirement-created') push RequirementRecord
 * （status='draft'，sourceSessionId=windowKey，actor={kind:'human'}——弹框作答
 * = 用户确认，语义等同看板 confirm）。幂等：mutator 内窗口已 bound → return
 * undefined 中止；中止后若快照显示已绑定 → REQBOARD_WINDOW_BOUND 拒绝。
 */
async function createRequirementDirect(
  deps: ReqboardToolDeps,
  windowKey: string,
  input: { title: string; category: RequirementCategory; description: string; reason: string },
): Promise<RequirementRecord> {
  const nowTs = deps.now()
  const result = await deps.store.mutate('requirement-created', (ledger) => {
    if (isWindowBound(ledger, windowKey)) return undefined // 幂等：已绑定 → 不重复立项
    const actor = { kind: 'human' } as const
    const req: RequirementRecord = {
      id: newRequirementId(),
      title: input.title,
      description: input.description,
      category: input.category,
      sourceSessionId: windowKey,
      status: 'draft',
      blocked: false,
      comments: [
        {
          id: newCommentId(),
          body: [
            `[会话捕获] 用户经两问弹框确认立项（会话 ${windowKey}）`,
            `名称/分类为用户确认值：${input.title}（${input.category}）`,
            ...(input.reason ? [`依据：${input.reason}`] : []),
          ].join('\n'),
          createdAt: nowTs,
          createdBy: actor,
        },
      ],
      version: 1,
      createdAt: nowTs,
      updatedAt: nowTs,
      createdBy: actor,
      updatedBy: actor,
    }
    ledger.requirements.push(req)
    return { requirements: [req] }
  })
  if (result.changed.requirements.length > 0) return result.changed.requirements[0]
  if (openRequirementsFor(result.ledger, windowKey).length > 0) {
    reject('reqboard_create 未写入：本窗口已绑定进行中需求，勿重复立项', 'REQBOARD_WINDOW_BOUND')
  }
  reject('reqboard_create 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
}

/** 需求简要投影（open_requirements 输出用；不泄漏 comments 等内部字段）。 */
function projectRequirement(r: RequirementRecord): { id: string; title: string; status: string; category: string } {
  return {
    id: r.id,
    title: r.title,
    status: r.status,
    category: r.category ?? '',
  }
}

const renderJson = (_args: unknown, value: unknown) => [
  { type: 'text', text: JSON.stringify(value, null, 2) },
]

/**
 * reqboard_create：识别到值得立项的新工作 →（弹框作答即立项门）→ 直接建 REQ。
 * 认证链：identity → live driver → direct human（服务缺失逐级降级）。
 */
export function defineCreateTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_create',
    description:
      '创建即立项：识别到值得立项的新工作（feature/bug/doc/refactor/spike/chore）时直接创建需求。'
      + '调用前必须先 ask_user_question 弹「两问确认」向用户确认：问题一需求名称（按对话/消息'
      + '上下文给出候选选项，最贴切一项置首标注 (Recommended)，允许用户自定义输入）；问题二需求'
      + '类型（选项 feature/bug/doc/refactor/spike/chore，(Recommended) 置首、可改选）。'
      + '用户作答 = 立项确认（无需任何待归类/建议卡中间态）——随后按用户确认值调用本工具：'
      + 'title=用户确认的需求名称、category=用户选择的需求类型、summary=工作摘要、reason=立项依据。'
      + '创建后 REQ 立即在看板 draft 泳道可见、本窗口绑定该需求。'
      + '调用前先 reqboard_status 自查：本窗口已绑定进行中需求或已有 pending 建议时不要重复立项。'
      + '仅闲聊、追问进度、或用户在自主回合（非直接消息）时不提议不立项。',
    parameters: {
      title: {
        type: 'string',
        description: '需求名称（用户两问弹框确认值，≤120 字符；人工确认时可改）',
        required: true,
      },
      category: {
        type: 'string',
        description: '需求分类：feature / bug / doc / refactor / spike / chore',
        required: true,
        enum: [...ALL_REQ_CATEGORIES],
      },
      summary: {
        type: 'string',
        description: '工作摘要（≤4000 字符；将作为需求描述底稿，留空则用 title 兜底）',
      },
      reason: {
        type: 'string',
        description: '立项依据（≤4000 字符）：为什么值得立项，供人工判断',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean', description: '是否成功' },
          requirement_id: { type: 'string', description: '新需求 id（REQ-xxxxxx）' },
          title: { type: 'string', description: '需求名称' },
          category: { type: 'string', description: '需求分类' },
          status: { type: 'string', description: '需求状态（draft）' },
          note: { type: 'string', description: '后续流程说明' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      requireDirectHuman(deps, exec)
      const a = (args ?? {}) as { title?: unknown; category?: unknown; summary?: unknown; reason?: unknown }
      const title = normalizeTitle(a.title)
      const category = asReqCategory(a.category)
      const summary = normalizeText(a.summary, 'summary')
      const reason = normalizeText(a.reason, 'reason')
      const req = await createRequirementDirect(deps, windowKey, {
        title,
        category,
        description: summary.length > 0 ? summary : title,
        reason,
      })
      return {
        success: true,
        requirement_id: req.id,
        title: req.title,
        category: req.category ?? category,
        status: req.status,
        note: '已直接立项（创建即立项）：REQ 已在看板 draft 泳道立即可见，本窗口已绑定',
      }
    },
  } as any)
}

/**
 * reqboard_status：只读投影（该窗口 open 需求 + 遗留 pending triage），立项前自查。
 * 认证：identity 即可（只读，不要求 live/direct-human）。
 */
export function defineStatusTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_status',
    description:
      '查询本窗口 reqboard 绑定状态：是否已绑定进行中需求、有无遗留待确认建议卡。'
      + '识别到新工作想立项前先自查：已绑定或有 pending 建议时不要重复立项。',
    parameters: {},
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          window_key: { type: 'string', description: '本窗口标识' },
          bound: { type: 'boolean', description: '本窗口是否已绑定进行中需求（bound 时不再立项）' },
          open_count: { type: 'number', description: '本窗口进行中需求数' },
          open_requirements: {
            type: 'array',
            description: '本窗口进行中需求简要列表',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                id: { type: 'string' },
                title: { type: 'string' },
                status: { type: 'string' },
                category: { type: 'string' },
              },
            },
          },
          has_pending: { type: 'boolean', description: '本窗口是否已有遗留待确认建议卡（旧流程 triage）' },
          pending_triage_id: { type: 'string', description: '最近遗留 pending triage id（无则空串）' },
          note: { type: 'string', description: '下一步指引' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (_args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      const ledger = await deps.store.read((l) => l)
      const open = openRequirementsFor(ledger, windowKey)
      const pending = findPending(ledger, windowKey)
      return {
        window_key: windowKey,
        bound: open.length > 0,
        open_count: open.length,
        open_requirements: open.map(projectRequirement),
        has_pending: pending !== undefined,
        pending_triage_id: pending?.id ?? '',
        note:
          open.length > 0
            ? '本窗口已绑定进行中需求，聚焦推进，勿重复立项'
            : pending !== undefined
              ? '存在遗留待确认建议卡（旧流程产物）：可在看板确认/拒绝，或忽略；新立项直接走 reqboard_create'
              : '本窗口未绑定需求：识别到值得立项的新工作 → 先 ask_user_question 弹「两问确认」（需求名称+需求类型）获用户确认，再按确认值调 reqboard_create 直接立项（创建即立项）',
      }
    },
  } as any)
}
/**
 * reqboard_move：推进本窗口**绑定需求**的状态（窗口侧唯一的状态推进入口）。
 *
 * 为什么需要它：台账状态此前只能由人在看板点按钮推进（GUI move-req），窗口 agent
 * 没有任何推进手段——需求建卡后即静止。本工具把「窗口推进自己的需求」变成一次
 * 工具调用，闸门仍然代码级生效：
 *   - 人工闸门（评审通过 reviewing>decomposing / 拆分确认 decomposing>implementing /
 *     验收通过 accepting>done / 归档 done>archived）→ 抛 human_gate，工具返回明确
 *     指引「该转移需人在项目看板点击确认」；
 *   - 非法转移 → invalid_transition；
 *   - 只能推进**本窗口绑定**的需求（防越权推进他窗口需求）。
 *
 * 典型用法：agent 完成方案设计 → move 到 reviewing；人确认方案后 agent 拆分任务卡
 * 落库（task/create）→ 全部任务 done 时 rollup 自动进 accepting（无需调用本工具）。
 *
 * 认证：identity + live driver（与 create 一致），不要求 direct-human——推进是执行
 * 窗口的常规工作动作，但人工闸门由协议层拒绝，故无越权风险。
 */
export function defineMoveTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_move',
    description:
      '推进本窗口已绑定需求的状态（项目看板泳道）。仅能推进本窗口绑定的需求；'
      + '人工闸门转移（评审通过/拆分确认/验收通过/归档）会被拒绝——那几步必须人在看板点确认。'
      + '用法：先 reqboard_status 确认绑定需求与当前状态，再 move 到目标状态并给 reason。',
    parameters: {
      to: {
        type: 'string',
        description: '目标状态：draft / reviewing / decomposing / implementing / accepting / done / archived / canceled',
        required: true,
        enum: [...ALL_REQ_STATUSES],
      },
      requirement_id: {
        type: 'string',
        description: '需求 id（REQ-xxxxxx）；不传则默认本窗口绑定的那条 open 需求',
      },
      reason: {
        type: 'string',
        description: '推进理由（≤500 字符，写入需求评论供复盘）',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          from: { type: 'string', description: '推进前状态' },
          to: { type: 'string', description: '推进后状态' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { to?: unknown; requirement_id?: unknown; reason?: unknown }
      const to = asReqStatus(a.to)
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const reason = normalizeText(a.reason, 'reason', 500)

      const snapshot = deps.store.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) {
        reject('reqboard_move 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      }
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (target === undefined) {
        reject(
          `reqboard_move 未执行：需求 ${explicitId} 不是本窗口绑定的进行中需求（只能推进自己的需求）`,
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }

      const from = target.status
      try {
        assertReqTransition(from, to, 'agent')
      } catch (err) {
        const code = (err as { code?: string }).code ?? 'invalid_transition'
        if (code === 'human_gate') {
          reject(
            `reqboard_move 未执行：${from} → ${to} 是人工闸门（需人在项目看板点击确认，agent 不可代替）`,
            'REQBOARD_HUMAN_GATE',
          )
        }
        reject(`reqboard_move 未执行：${(err as Error).message}`, code)
      }

      const result = await deps.store.mutate('requirement-moved', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        assertReqTransition(req.status, to, 'agent')
        req.status = to
        req.version += 1
        req.updatedAt = deps.now()
        req.updatedBy = { kind: 'agent', sessionId: windowKey }
        req.comments.push({
          id: newCommentId(),
          body: `[窗口推进] ${from} → ${to}${reason ? `：${reason}` : ''}（窗口 ${windowKey}）`,
          createdAt: deps.now(),
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        // 推进到 implementing 时顺带重算（任务可能已全部完成）
        const advanced = applyTaskRollup(ledger, { now: deps.now(), commentId: () => newCommentId() }, req.id)
        return { requirements: [req, ...advanced] }
      })
      const changed = result.changed.requirements[0]
      if (changed === undefined) {
        reject('reqboard_move 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      }
      return {
        success: true,
        requirement_id: changed.id,
        from,
        to: changed.status,
        note:
          changed.status === to
            ? `已推进：${from} → ${to}`
            : `已推进：${from} → ${changed.status}（派生规则顺带推进）`,
      }
    },
  } as any)
}
