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
import { appendFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { isWindowBound, pendingSuggestionFor, openRequirementsFor } from './capture.js';
import { applyTaskRollup } from './rollup.js';
import { toolActivitySince, evidenceMatchesRecentUserMsg, type ToolTraceEntry, type RecentUserMsg } from './capture-hook.js';
import { applyVerdicts } from './verdicts.js';
import { registerArtifact, artifactNotifyText, assertArtifactGates } from './artifact-gates.js';
import type { ReqboardStore } from './store.js';
import type {
  ReqboardLedger,
  RequirementCategory,
  RequirementRecord,
  RequirementStatus,
  StageArtifact,
  TriageRecord,
} from '../shared/protocol.js';
import {
  ALL_ARTIFACT_KINDS,
  ALL_REQ_CATEGORIES,
  ARTIFACT_CONFIRM_GATES,
  canReqTransition,
  ARCHIVE_DOC_RULES,
  assertArchiveMaterials,
  ALL_REQ_STATUSES,
  ALL_TASK_PHASES,
  ALL_TASK_SIDES,
  ALL_TASK_STATUSES,
  asReqCategory,
  asReqStatus,
  asScope,
  assertDagAcyclic,
  assertReqTransition,
  assertTaskTransition,
  HUMAN_ONLY_REQ_TRANSITIONS,
  REQ_TRANSITIONS,
  newCommentId,
  newExecutionId,
  newRequirementId,
  newTaskId,
  normalizePlanTasks,
  normalizeText,
  normalizeTitle,
  planApproved,
  recordStatus,
  type PlanTask,
  type VerificationItem,
  type VerificationSheet,
  type TaskRecord,
} from '../shared/protocol.js';

/** 结构化认证失败：message 自带（CODE）文本；code 属性仅测试/直接执行消费。 */
function reject(message: string, code: string): never {
  throw Object.assign(new Error(`${message}（${code}）`), { code })
}

/**
 * 阶段通知简版（REQ-31e11f t4）：产物登记成功时通知请人审阅。
 * 用 ctx 里可用的通知通道（feishu_notify）；若无通知服务则 logger.info 降级，不阻断。
 */
function notifyArtifactRegistered(
  deps: ReqboardToolDeps,
  reqId: string,
  artifact: StageArtifact,
): void {
  try {
    const text = artifactNotifyText(
      { id: reqId, title: '' } as RequirementRecord,
      artifact,
    )
    // 尝试通过全局 logger 输出（降级路径，不阻断）
    const g = globalThis as { console?: typeof console }
    g.console?.info?.('[reqboard] ' + text)
  } catch { /* 通知失败不阻断主流程 */ }
}

/** 工具依赖：store 强依赖；agents/sessionProjections 为惰性服务访问器（缺失 → 认证降级）。 */
export interface ReqboardToolDeps {
  store: ReqboardStore
  now: () => number
  /** 当前 agents 服务（unavailable → undefined）。 */
  agents?: () => unknown
  /** 当前 sessionProjections 服务（unavailable → undefined）。 */
  sessionProjections?: () => unknown
  /** 工具痕迹表（REQ-2e9473 t05/t06）：done 凭证门判定开工以来有无真实工具动作。可选。 */
  toolTrace?: Map<string, ToolTraceEntry[]>
  /** done 批量关闭节流窗口（毫秒，默认 60000；测试可注入 0 关闭）。 */
  doneThrottleMs?: number
  /** userQuestions 弹框服务（REQ-2e9473 t07 ask_confirm；缺失 → ask_confirm 降级 fallback=board）。 */
  userQuestions?: () => unknown
  /** 最近用户消息缓冲（REQ-2e9473 t10 文字确认核验；缺失 → 核验降级放行并在返回中注明）。 */
  recentUserMsgs?: Map<string, RecentUserMsg[]>
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
/**
 * rollup 阻塞清单（REQ-2e9473 t02）：需求停在 implementing 但 R2 无法推进（存在未完成任务）
 * 时，返回阻塞任务清单；否则 undefined。用于 task_move / verify_submit 返回体显式告警——
 * REQ-6f39b5 事故 B 的教训：幽灵任务卡死 rollup 时静默无提示，agent 与用户都看不见。
 */
function rollupBlockersOf(
  ledger: ReqboardLedger,
  reqId: string,
  reqStatus: string,
): { id: string; title: string; status: string }[] | undefined {
  if (reqStatus !== 'implementing') return undefined
  const open = ledger.tasks.filter(t => t.requirementId === reqId && t.status !== 'canceled' && t.status !== 'done')
  if (open.length === 0) return undefined
  return open.map(t => ({ id: t.id, title: t.title, status: t.status }))
}

/**
 * done 凭证门（REQ-2e9473 t06/W2，事故 C/D 的硬门）：转 done 前的四重校验——
 *  ① 汇报前置：必须有 task_report 留痕（lastReport），且 completed/filesChanged 至少其一非空；
 *  ② 真实动作：开工（claimedAt）以来有干活类工具痕迹（edit/write/bash/run_code，弱信号），
 *     或汇报声明的文件真实存在且 mtime 新于开工（强信号）——25ms 速通两路都过不了；
 *  ③ 批量关闭节流：同需求 60s 内已有其他任务被本窗口关闭 → 拒（事故 C：一次调用关 4 个任务）；
 *  ④ 构建新鲜度：汇报改动涉及 packages/pages/<pkg>/src/ → 该包 lib/client.js 必须存在且
 *     新于最新 src 改动（事故 D：改了源码没构建，用户看到旧页面）。
 */
function assertDoneEvidence(
  deps: ReqboardToolDeps,
  windowKey: string,
  task: TaskRecord,
  ledger: ReqboardLedger,
): void {
  // ① 汇报前置 + 证据非空
  const rep = task.lastReport
  if (rep === undefined) {
    reject(
      'reqboard_task_move 未执行：done 凭证门——该任务还没有 reqboard_task_report 汇报。'
      + '先汇报（summary/completed/files_changed）再关闭（REQ-2e9473 W2，事故 C 修复）',
      'REQBOARD_NO_REPORT',
    )
  }
  if (rep.filesChanged.length === 0 && rep.completed.length === 0) {
    reject(
      'reqboard_task_move 未执行：done 凭证门——汇报证据为空（completed 与 files_changed 至少其一非空），空汇报不算完工',
      'REQBOARD_NO_REPORT',
    )
  }
  // ② 真实动作：工具痕迹（弱信号）或文件证据（强信号）
  const since = task.claimedAt ?? task.createdAt
  const activity = deps.toolTrace === undefined ? undefined : toolActivitySince(deps.toolTrace, windowKey, since)
  const hasTraceWork = activity !== undefined && activity.workLike > 0
  const fileEvidence = rep.filesChanged.some((f) => {
    try { return statSync(join(process.cwd(), f)).mtimeMs >= since } catch { return false }
  })
  if (!hasTraceWork && !fileEvidence) {
    reject(
      'reqboard_task_move 未执行：done 凭证门——开工以来无干活类工具动作，且汇报声明的改动文件不存在或早于开工时间。'
      + '凭证不足不能关闭（25ms 速通拦截）',
      'REQBOARD_NO_EVIDENCE',
    )
  }
  // ③ 批量关闭节流：同需求 60s 内已有其他任务被 agent 关闭
  const nowTs = deps.now()
  const throttleMs = deps.doneThrottleMs ?? 60_000
  const recentDone = ledger.tasks.find(t =>
    t.id !== task.id
    && t.requirementId === task.requirementId
    && (t.statusHistory ?? []).some(h => h.status === 'done' && h.by.kind === 'agent' && nowTs - h.at < throttleMs),
  )
  if (recentDone !== undefined) {
    reject(
      'reqboard_task_move 未执行：done 凭证门——60 秒内刚关闭了任务 ' + recentDone.id + '（' + recentDone.title + '）。'
      + '禁止批量关闭：逐任务验收，稍后再试（事故 C 修复）',
      'REQBOARD_BULK_CLOSE',
    )
  }
  // ④ 页面插件构建新鲜度（事故 D）
  const pagesSrc = rep.filesChanged.filter(f => /^packages\/pages\/[^/]+\/src\//.test(f))
  if (pagesSrc.length > 0) {
    const pkg = /^packages\/pages\/([^/]+)\//.exec(pagesSrc[0])?.[1] ?? ''
    const clientJs = join(process.cwd(), 'packages/pages', pkg, 'lib/client.js')
    let clientMtime = 0
    try { clientMtime = statSync(clientJs).mtimeMs } catch {
      reject(
        'reqboard_task_move 未执行：done 凭证门——页面插件任务未构建：packages/pages/' + pkg + '/lib/client.js 不存在。'
        + '先 cd packages/pages/' + pkg + ' && pnpm build:client（事故 D：改了源码 ≠ 已生效）',
        'REQBOARD_STALE_BUILD',
      )
    }
    const newestSrc = Math.max(...pagesSrc.map((f) => {
      try { return statSync(join(process.cwd(), f)).mtimeMs } catch { return 0 }
    }))
    if (clientMtime < newestSrc) {
      reject(
        'reqboard_task_move 未执行：done 凭证门——构建产物陈旧：packages/pages/' + pkg + '/lib/client.js 旧于 src 最新改动。'
        + '先重新 pnpm build:client 再关任务（事故 D：改了源码 ≠ 已生效）',
        'REQBOARD_STALE_BUILD',
      )
    }
  }
}

/**
 * evidence 中的工作区路径候选（REQ-2e9473 t12）：只认已知根前缀 + 扩展名的 token，
 * 降低把散文误判成路径的概率（如"packages/x.ts 通过"仅取 packages/x.ts）。
 */
function workspacePathCandidates(evidence: readonly string[]): string[] {
  // 注意扩展名按长度降序：json 必须在 js 之前，否则 package.json 会被截成 package.js（t12 实测）
  const re = /(?:^|[\s（(])((?:packages|docs|scripts|tests|agent-dh|profiles|examples)\/[\w./@-]+\.(?:tsx|json|mjs|cjs|jpeg|html|svg|png|jpg|css|ts|js|md))/g
  const out = new Set<string>()
  for (const e of evidence) {
    for (const m of e.matchAll(re)) {
      if (m[1] !== undefined) out.add(m[1])
    }
  }
  return [...out]
}

/**
 * 闸门问题卡（REQ-2e9473 t08）：move 被人工闸门拒绝时，返回可直接喂给 reqboard_ask_confirm
 * 的调用参数——闸门从"只挡不引"升级为"挡并指路"。用户点肯定项即自动落章+推进。
 */
function gateQuestionCard(gateKind: string | undefined, from: string, to: string): string {
  const questionByTransition: Record<string, string> = {
    'brainstorming>planning': '需求文档已完成，是否确认进入技术设计？',
    'planning>decomposing': '实施计划已提交，是否批准进入拆分？',
    'decomposing>implementing': '拆分清单已落库，是否确认进入实施？',
    'accepting>archived': '验收材料已提交，是否验收通过并归档？',
  }
  const question = questionByTransition[from + '>' + to] ?? ('是否确认推进到 ' + to + '？')
  const call = gateKind === 'plan' || (from === 'planning' && to === 'decomposing')
    ? '{ target: \'plan\', question: \'' + question + '\' }'
    : '{ target: \'artifact\', kind: \'' + (gateKind ?? 'requirement') + '\', question: \'' + question + '\' }'
  return '\n【问题卡】直接调 reqboard_ask_confirm 完成确认（用户点肯定项 → 自动落章并推进 ' + from + ' → ' + to + '）：\n  reqboard_ask_confirm(' + call + ')'
}

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

/** agent 从当前状态可自行推进的目标（排除人工闸门：取消/归档）。 */
function agentNextActions(status: RequirementStatus): RequirementStatus[] {
  return [...REQ_TRANSITIONS[status]].filter((to) => !HUMAN_ONLY_REQ_TRANSITIONS.has(`${status}>${to}`))
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
          next_actions: {
            type: 'array',
            description: '本窗口可自行推进的目标状态（agent 合法转移；取消/归档为人工闸门不在此列）',
            items: { type: 'string' },
          },
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
        next_actions: open.length > 0 ? agentNextActions(open[0].status) : [],
        note:
          open.length > 0
            ? `本窗口已绑定进行中需求（当前 ${open[0].status}）：里程碑处用 reqboard_move 自行推进（${agentNextActions(open[0].status).join(' / ') || '无可推进项'}），勿重复立项`
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
 *   - 人工闸门（评审通过 brainstorming>decomposing / 拆分确认 decomposing>implementing /
 *     验收通过 accepting>done / 归档 done>archived）→ 抛 human_gate，工具返回明确
 *     指引「该转移需人在项目看板点击确认」；
 *   - 非法转移 → invalid_transition；
 *   - 只能推进**本窗口绑定**的需求（防越权推进他窗口需求）。
 *
 * 典型用法：agent 完成方案设计 → move 到 brainstorming；人确认方案后 agent 拆分任务卡
 * 落库（task/create）→ 全部任务 done 时 rollup 自动进 accepting（无需调用本工具）。
 *
 * 认证：identity + live driver（与 create 一致），不要求 direct-human——推进是执行
 * 窗口的常规工作动作，但人工闸门由协议层拒绝，故无越权风险。
 */
export function defineMoveTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_move',
    description:
      '推进本窗口已绑定需求的状态（项目看板泳道）——状态由执行窗口自己维护，不要等用户手动点。'
      + '仅能推进本窗口绑定的需求；在途状态（评审→拆分→实施→验收）都可自行推进，'
      + '只有「取消需求」「归档」是人工闸门（调用会被代码级拒绝并提示）。'
      + '用法：里程碑处调用（方案定 → decomposing，开工 → implementing，交付 → accepting），'
      + 'reason 写清做了什么（进需求留痕供验收与复盘）；先 reqboard_status 可查当前状态与可选动作。',
    parameters: {
      to: {
        type: 'string',
        description: '目标状态：draft / brainstorming / decomposing / implementing / accepting / done / archived / canceled',
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
          doc_sync_pending: {
            type: 'array',
            description: '待同步的下游文档（重交下游产物后销标）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                source: { type: 'string' },
                downstream: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          doc_sync_warning: { type: 'string' },
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
      // ── REQ-ff20ca t3：产物确认型人工门的判定，从"谁调用"改为"产物是否已确认" ──
      // 语义内核不变（仍须人确认），但确认来源不限：看板一键确认 或 会话经
      // ask_user_question 落章（reqboard_confirm_artifact）——后者此前无法让门开启。
      const gateKind = ARTIFACT_CONFIRM_GATES[`${from}>${to}`]
      const gateConfirmed = gateKind !== undefined
        && (target.artifacts ?? []).some(x => x.kind === gateKind && x.confirmedAt !== undefined)
      if (gateConfirmed && HUMAN_ONLY_REQ_TRANSITIONS.has(`${from}>${to}`)) {
        // 门已开启（确认动作已由人完成）：只校验转移合法性，不再受 human_gate 限制
        if (!canReqTransition(from, to)) {
          reject(`reqboard_move 未执行：需求状态不允许从 ${from} 转移到 ${to}`, 'REQBOARD_INVALID_TRANSITION')
        }
      } else {
        try {
          assertReqTransition(from, to, 'agent')
        } catch (err) {
          const code = (err as { code?: string }).code ?? 'invalid_transition'
          if (code === 'human_gate') {
            const need = gateKind !== undefined ? `（kind=${gateKind}）` : ''
            reject(
              `reqboard_move 未执行：${from} → ${to} 需要人确认产物${need}。`
              + '首选：调 reqboard_ask_confirm 弹框请人确认（肯定答复自动落章+推进）；'
              + '兜底：用户在项目看板一键确认。'
              + '（取消/验收通过/归档类决定仍只能由人操作）'
              + gateQuestionCard(gateKind, from, to),
              'REQBOARD_HUMAN_GATE',
            )
          }
          reject(`reqboard_move 未执行：${(err as Error).message}`, code)
        }
      }
      // ── 产物闸门（存在 + 已确认）：agent 侧此前缺失，本次补齐（与看板 API 同源）──
      const gateFailure = assertArtifactGates(target, from, to)
      if (gateFailure !== undefined) {
        const hint = gateFailure.code === 'artifact_not_confirmed'
          ? '；首选调 reqboard_ask_confirm 弹框请人确认（自动落章+推进），兜底用户看板一键确认'
            + gateQuestionCard(gateFailure.kind, from, to)
          : ''
        reject(
          `reqboard_move 未执行：${gateFailure.message}${hint}`,
          gateFailure.code === 'artifact_not_confirmed' ? 'REQBOARD_ARTIFACT_NOT_CONFIRMED' : 'REQBOARD_MISSING_ARTIFACT',
        )
      }

      const result = await deps.store.mutate('requirement-moved', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        // 与外部同款判定（并发下 req.status 可能与外部快照不同）
        const innerKey = `${req.status}>${to}`
        const innerKind = ARTIFACT_CONFIRM_GATES[innerKey]
        const innerConfirmed = innerKind !== undefined
          && (req.artifacts ?? []).some(x => x.kind === innerKind && x.confirmedAt !== undefined)
        if (innerConfirmed && HUMAN_ONLY_REQ_TRANSITIONS.has(innerKey)) {
          if (!canReqTransition(req.status, to)) {
            throw Object.assign(new Error(`需求状态不允许从 ${req.status} 转移到 ${to}`), { code: 'invalid_transition' })
          }
        } else {
          assertReqTransition(req.status, to, 'agent')
        }
        req.status = to
        req.version += 1
        req.updatedAt = deps.now()
        req.updatedBy = { kind: 'agent', sessionId: windowKey }
        recordStatus(req, to, req.updatedAt, { kind: 'agent', sessionId: windowKey }, reason || undefined)
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
      // 文档待同步警告（REQ-2e9473 t19/W8）：未销标时推进给出可见提示
      const pendingSync = deps.store.snapshot().requirements.find(r => r.id === changed.id)?.docSyncPending ?? []
      return {
        success: true,
        requirement_id: changed.id,
        from,
        to: changed.status,
        ...(pendingSync.length > 0
          ? {
              doc_sync_pending: pendingSync,
              doc_sync_warning: '⏳ 文档待同步：' + pendingSync.map(p => p.source + '→' + (p.downstream.join('/') || '-')).join('；') + '（重交下游文档后销标）',
            }
          : {}),
        note:
          changed.status === to
            ? `已推进：${from} → ${to}`
            : `已推进：${from} → ${changed.status}（派生规则顺带推进）`,
      }
    },
  } as any)
}

/**
 * reqboard_decompose —— 真拆分：把绑定需求拆成任务 DAG 并**落库**。
 *
 * 为什么需要它（用户提问「拆分是真拆分吗」）：拆分态此前只是一个状态名——没有任何
 * 代码把需求变成任务，台账 tasks 恒为 0，看板任务页与甘特图自然无从谈起。本工具把
 * 「拆」变成一次真实写入：一次调用落库 N 张任务卡（含 DAG 依赖），随后 rollup 自动
 * 把需求推进到拆分/实施态，任务页与甘特图立即有数据。
 *
 * 拆分粒度由窗口 agent 自己决定（它就是干活的人），工具只负责**结构正确**：
 *   - 只能对**本窗口绑定**需求拆分（防越权）；
 *   - 状态必须是评审/拆分/实施（draft 说明方案还没讨论；终态不可再拆）；
 *   - 依赖用批次内 key 引用（工具负责映射成真实任务 id），落库前过 DAG 校验（无环/无悬空）。
 */
export function defineDecomposeTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_decompose',
    description:
      '拆分落库（plan mode 的执行端）：把**已获人批准的实施计划**写成任务卡——'
      + '任务立即出现在看板「任务」页与甘特图里。默认不传 tasks = 直接落库批准的计划；'
      + '传 tasks 则 key 集合必须与批准的计划一致（防止「批了 A 落库 B」）。'
      + '前置条件：需求属于本窗口、处于评审/拆分/实施态，且计划已由人批准——'
      + '没有计划或计划未批准会被代码级拒绝（REQBOARD_PLAN_NOT_APPROVED）：'
      + '先 reqboard_plan_submit 提交计划，请人在看板点「批准计划」。',
    parameters: {
      requirement_id: {
        type: 'string',
        description: '需求 id（REQ-xxxxxx）；不传则默认本窗口绑定的那条需求',
      },
      tasks: {
        type: 'array',
        description: '任务清单。W7 边界：计划未含任务表时必传（本工具即任务卡创作口，每卡须含 implementation+可证伪 acceptance）；计划已含任务表时可不传（落库批准的计划）或传（key 须与计划一致）',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            key: { type: 'string', description: '批次内引用键（如 t1；depends_on 用它引用）' },
            title: { type: 'string', description: '任务标题（≤120 字符，动词开头）' },
            description: { type: 'string', description: '任务说明' },
            phase: {
              type: 'string',
              description: '流水线阶段：doc / ui / analysis / implement / test / review / merge',
              enum: [...ALL_TASK_PHASES],
            },
            side: {
              type: 'string',
              description: '端侧：frontend / backend / fullstack / doc',
              enum: [...ALL_TASK_SIDES],
            },
            depends_on: {
              type: 'array',
              description: '依赖：同批任务的 key 或已存在任务 id（无依赖不传）',
              items: { type: 'string' },
            },
            acceptance: { type: 'string', description: '验收标准（可证伪：跑什么、看到什么算过）' },
            implementation: { type: 'string', description: '实施方案（W7 任务卡创作必填：改哪些文件、步骤、验证方式）' },
            context: { type: 'string', description: '需求背景摘要（自足执行用）' },
            skip_integration: { type: 'boolean', description: '是否跳过联调（默认按 side 推导）' },
          },
        },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          requirement_status: { type: 'string', description: '拆分后需求状态（rollup 可能已推进）' },
          created: {
            type: 'array',
            description: '落库的任务（key → 真实任务 id）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                key: { type: 'string' },
                id: { type: 'string' },
                title: { type: 'string' },
                depends_on: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          thin_cards: { type: 'array', items: { type: 'string' }, description: '缺实施方案的薄卡（历史批准计划）' },
          warning: { type: 'string' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 20000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; tasks?: unknown }
      if (a.tasks !== undefined && (!Array.isArray(a.tasks) || a.tasks.length === 0)) {
        reject('reqboard_decompose 未执行：tasks 传了就必须是非空数组（不传 = 直接落库已批准的计划）', 'REQBOARD_INVALID_INPUT')
      }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)

      const snapshot = deps.store.snapshot()
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
      // 批准（reqboard_ask_confirm target=plan）会**自动**把 planning → decomposing，于是正常
      // 路径必然先到 decomposing 再调 decompose → 被自己的守卫拒死，审批流水线自锁。
      // 正解：幽灵任务的唯一判据是"已有任务"（防线②），状态只用于区分"是否已越过拆分"。
      if (target.status === 'implementing' || target.status === 'accepting') {
        reject(
          'reqboard_decompose 未执行：需求已处于 ' + target.status + '（拆分已完成），'
          + '重复拆分会产生重复任务。要调整任务请逐任务修改，或人工取消后重拆',
          'REQBOARD_ALREADY_DECOMPOSED',
        )
      }
      const existingTasks = snapshot.tasks.filter(t => t.requirementId === target.id && t.status !== 'canceled')
      if (existingTasks.length > 0) {
        const list = existingTasks.map(t => t.id + ' ' + t.title + '（' + t.status + '）').join('；')
        reject(
          'reqboard_decompose 未执行：该需求已落库 ' + existingTasks.length + ' 个未取消任务，禁止重复拆分。已有任务：' + list,
          'REQBOARD_ALREADY_DECOMPOSED',
        )
      }

      // ── 计划闸门（plan mode 的代码级 HARD GATE）──────────────────────────
      // 拆分不是自由创作：落库的必须是**人已经批准过**的那张任务表。没有计划或计划未
      // 批准 → 直接拒绝（agent 无法自行越过；人批准是唯一钥匙）。
      if (!planApproved(target)) {
        reject(
          'reqboard_decompose 未执行：该需求还没有已批准的实施计划。'
          + '计划模式要求：先 reqboard_plan_submit 提交计划（文档路径 + 摘要 + 任务表），'
          + '请人在项目看板点「批准计划」，批准后才能拆分落库',
          'REQBOARD_PLAN_NOT_APPROVED',
        )
      }
      const planTasks: PlanTask[] = target.plan?.tasks ?? []
      // ── W7 阶段产物边界（REQ-2e9473 t17）：两条路径 ─────────────────────
      //  路径 A（创作型，W7 新语义）：计划只含技术设计（tasks 空）→ decompose 承担任务卡
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
            'reqboard_decompose 未执行：技术设计未含任务表（W7 新语义）——请传入 tasks 创作任务卡'
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

      const nowTs = deps.now()
      try {
        const result = await deps.store.mutate('task-created', (ledger) => {
          const req = ledger.requirements.find(r => r.id === target.id)
          if (req === undefined) return undefined
          const used = new Set(ledger.tasks.map(t => t.id))
          const idByKey = new Map<string, string>()
          const records: TaskRecord[] = []
          const commentLines: string[] = []
          for (const d of draft) {
            let id = newTaskId()
            for (let guard = 0; guard < 50 && used.has(id); guard++) id = newTaskId()
            used.add(id)
            idByKey.set(d.key, id)
            const record: TaskRecord = {
              id,
              requirementId: req.id,
              title: d.title,
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
          // 销标（REQ-2e9473 t19/W8）：拆分重做即完成 decomposition 同步
          req.docSyncPending = (req.docSyncPending ?? []).filter(p => !p.downstream.includes('decomposition'))
          for (const r of records) {
            const deps = r.dependsOn.length > 0 ? '（依赖 ' + r.dependsOn.join(', ') + '）' : ''
            commentLines.push('- ' + r.id + ' ' + r.title + deps)
          }
          req.comments.push({
            id: newCommentId(),
            body:
              '[拆分] 按已批准的实施计划落库 ' + records.length + ' 个任务'
              + (req.plan !== undefined ? '（计划 ' + req.plan.path + '，批准于 ' + new Date(req.plan.approvedAt ?? 0).toISOString() + '）' : '')
              + '：\n' + commentLines.join('\n')
              + '\n（窗口 ' + windowKey + '）',
            createdAt: nowTs,
            createdBy: { kind: 'agent', sessionId: windowKey },
          })
          req.version += 1
          req.updatedAt = nowTs
          req.updatedBy = { kind: 'agent', sessionId: windowKey }
          const advanced = applyTaskRollup(ledger, { now: nowTs, commentId: () => newCommentId() }, req.id)
          return { tasks: records, requirements: [req, ...advanced] }
        })
        const req = result.changed.requirements[0]
        const created = result.changed.tasks.map((t, i) => ({
          key: draft[i]?.key ?? '',
          id: t.id,
          title: t.title,
          depends_on: [...t.dependsOn],
        }))
        // ── 产物登记（REQ-31e11f t4）：decomposition + 每任务 task_detail ──
        const reqDir = 'docs/requirements/' + target.id
        const decompPath = reqDir + '/decomposition.md'
        // 生成 decomposition.md（计划任务表 ↔ 落库任务 id 对照）
        const decompContent = [
          '# ' + target.id + ' 拆分清单（decomposition）',
          '',
          '> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照',
          '',
          '| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |',
          '|---------|--------|------|------|------|------|---------|',
          ...created.map(c => {
            const t = result.changed.tasks.find(x => x.id === c.id)!
            return '| ' + c.key + ' | ' + c.id + ' | ' + t.title + ' | ' + t.phase + ' | ' + t.side + ' | ' + (c.depends_on.join(', ') || '-') + ' | ' + (t.acceptance || '-') + ' |'
          }),
          '',
        ].join('\n')
        const decompAbs = join(process.cwd(), decompPath)
        if (!existsSync(decompAbs)) {
          mkdirSync(dirname(decompAbs), { recursive: true })
          writeFileSync(decompAbs, decompContent, 'utf8')
        }
        // 生成每任务自足任务卡骨架
        for (const c of created) {
          const t = result.changed.tasks.find(x => x.id === c.id)!
          const taskPath = reqDir + '/tasks/' + c.id + '.md'
          const taskAbs = join(process.cwd(), taskPath)
          if (!existsSync(taskAbs)) {
            mkdirSync(dirname(taskAbs), { recursive: true })
            const depTitles = c.depends_on.map(depId => {
              const dep = result.changed.tasks.find(x => x.id === depId)
              return dep ? dep.title : depId
            })
            const taskContent = [
              '# ' + c.id + ' ' + t.title,
              '',
              '> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件',
              '',
              '## 目标',
              t.title,
              '',
              '## 背景摘要（context）',
              t.context || '（待补充）',
              '',
              '## 范围',
              '- 阶段：' + t.phase,
              '- 端侧：' + t.side,
              ...(t.scope && (t.scope.apis.length > 0 || t.scope.tables.length > 0 || t.scope.files.length > 0)
                ? ['- APIs：' + t.scope.apis.join('、'), '- 表：' + t.scope.tables.join('、'), '- 文件：' + t.scope.files.join('、')]
                : []),
              '',
              '## 验收标准',
              t.acceptance || '（待补充）',
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
            writeFileSync(taskAbs, taskContent, 'utf8')
          }
        }
        // 登记产物
        await deps.store.mutate('requirement-updated', (ledger) => {
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
          note: '已落库 ' + created.length + ' 个任务。下一步：调 reqboard_ask_confirm（target=artifact, kind=decomposition）弹框请人确认拆分清单——确认后自动推进到 implementing；任务开工/完成用 reqboard_task_move（任务全部完成后需求自动进入验收）',
        }
      } catch (err) {
        const code = (err as { code?: string }).code ?? 'REQBOARD_INVALID_INPUT'
        reject('reqboard_decompose 未执行：' + ((err as Error).message ?? String(err)), code)
      }
    },
  } as any)
}

/**
 * reqboard_task_move —— 窗口推进**自己需求下**的任务状态。
 *
 * 为什么需要它：任务是干活的单位，没有它，agent 拆完任务就只能停在 todo——
 * 需求也就永远进不了验收（rollup 看的是任务事实）。人工闸门仅剩「取消/复活」。
 * 顺带结算执行段（进入 in_progress 开一段执行记录，离开时闭合），甘特图与耗时
 * 统计依赖这段真实数据。
 */
export function defineTaskMoveTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_task_move',
    description:
      '推进本窗口需求下的任务状态（todo → in_progress → integration/testing → in_review → done）。'
      + '开工时移到 in_progress（自动开一段执行记录），完成时移到 done；'
      + '任务全部 done 后需求会自动进入验收。'
      + '只有「取消任务/复活已取消任务」是人工闸门。',
    parameters: {
      task_id: { type: 'string', description: '任务 id（t-xxxxxx）', required: true },
      to: {
        type: 'string',
        description: '目标状态：todo / in_progress / integrating / testing / in_review / done / canceled',
        required: true,
        enum: [...ALL_TASK_STATUSES],
      },
      reason: { type: 'string', description: '推进理由（≤500 字符；写入任务留痕）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          requirement_id: { type: 'string' },
          from: { type: 'string' },
          to: { type: 'string' },
          requirement_status: { type: 'string' },
          task_card: {
            type: 'object',
            additionalProperties: false,
            description: '开工说明书：task_move→in_progress 时返回任务卡全文',
            properties: {
              title: { type: 'string' },
              description: { type: 'string' },
              acceptance: { type: 'string' },
              implementation: { type: 'string' },
              context: { type: 'string' },
              depends_on: { type: 'array', items: { type: 'string' } },
              doc_path: { type: 'string' },
            },
          },
          blockers: {
            type: 'array',
            description: '未完成任务清单（需求未进验收的原因）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                id: { type: 'string' },
                title: { type: 'string' },
                status: { type: 'string' },
              },
            },
          },
          warning: { type: 'string' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { task_id?: unknown; to?: unknown; reason?: unknown }
      const taskId = normalizeText(a.task_id, 'task_id', 64)
      const to = normalizeText(a.to, 'to', 32)
      const reason = normalizeText(a.reason, 'reason', 500)
      if (!(ALL_TASK_STATUSES as readonly string[]).includes(to)) {
        reject('reqboard_task_move 未执行：任务状态必须是 ' + ALL_TASK_STATUSES.join(', '), 'REQBOARD_INVALID_INPUT')
      }
      const snapshot = deps.store.snapshot()
      const task = snapshot.tasks.find(t => t.id === taskId)
      if (task === undefined) reject('reqboard_task_move 未执行：任务 ' + taskId + ' 不存在', 'REQBOARD_TASK_NOT_FOUND')
      const bound = openRequirementsFor(snapshot, windowKey)
      if (!bound.some(r => r.id === task.requirementId)) {
        reject('reqboard_task_move 未执行：任务 ' + taskId + ' 不属于本窗口绑定的需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }
      const from = task.status
      try {
        assertTaskTransition(from, to as TaskRecord['status'], 'agent')
      } catch (err) {
        const code = (err as { code?: string }).code ?? 'invalid_transition'
        if (code === 'human_gate') {
          reject('reqboard_task_move 未执行：' + from + ' → ' + to + ' 是人工闸门（仅人可操作）', 'REQBOARD_HUMAN_GATE')
        }
        reject('reqboard_task_move 未执行：' + ((err as Error).message ?? String(err)), code)
      }
      const nowTs = deps.now()
      const result = await deps.store.mutate('task-moved', (ledger) => {
        const t = ledger.tasks.find(x => x.id === taskId)
        if (t === undefined) return undefined
        assertTaskTransition(t.status, to as TaskRecord['status'], 'agent')
        // done 凭证门（REQ-2e9473 t06）：转移合法还不够，完工要有凭证
        if (to === 'done') assertDoneEvidence(deps, windowKey, t, ledger)
        t.status = to as TaskRecord['status']
        t.version += 1
        t.updatedAt = nowTs
        t.updatedBy = { kind: 'agent', sessionId: windowKey }
        if (to === 'in_progress') {
          t.claimedBy = windowKey
          t.claimedAt = nowTs
          t.executions.push({
            id: newExecutionId(),
            sessionId: windowKey,
            trigger: 'manual',
            startedAt: nowTs,
            outcome: 'running',
          })
        } else {
          for (const e of t.executions) {
            if (e.outcome === 'running') {
              e.endedAt = nowTs
              e.outcome = to === 'canceled' || to === 'todo' ? 'cancelled' : 'succeeded'
            }
          }
        }
        if (to === 'todo' || to === 'done' || to === 'canceled') {
          delete t.claimedBy
          delete t.claimedAt
        }
        recordStatus(t, to, nowTs, { kind: 'agent', sessionId: windowKey }, reason || undefined)
        if (reason.length > 0) {
          t.comments.push({
            id: newCommentId(),
            body: '[状态] → ' + to + '：' + reason + '（窗口 ' + windowKey + '）',
            createdAt: nowTs,
            createdBy: { kind: 'agent', sessionId: windowKey },
          })
        }
        const advanced = applyTaskRollup(ledger, { now: nowTs, commentId: () => newCommentId() }, t.requirementId)
        return { tasks: [t], requirements: advanced }
      })
      const changed = result.changed.tasks[0]
      if (changed === undefined) reject('reqboard_task_move 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // rollup 可能未推进需求（如 decomposing 停等人工确认门）——需求状态从台账现读，
      // 不只依赖 changed.requirements（仅含被推进的需求）
      const ledgerAfter = deps.store.snapshot()
      const reqAfter = ledgerAfter.requirements.find(r => r.id === changed.requirementId)
      // rollup 阻塞显式化（REQ-2e9473 t02）：需求停在 implementing 且有未完成任务 → 显式列出
      const blockers = reqAfter === undefined ? undefined : rollupBlockersOf(ledgerAfter, reqAfter.id, reqAfter.status)
      // 开工说明书送达（REQ-2e9473 t04/W5）：开工即拿到完整任务卡，不凭记忆回读设计文档——
      // REQ-6f39b5 事故 F：薄卡 + 不回读 = 8 处偏离技术设计。
      const taskCard = to === 'in_progress'
        ? {
            title: changed.title,
            description: changed.description,
            acceptance: changed.acceptance,
            implementation: changed.implementation ?? '',
            context: changed.context,
            depends_on: [...changed.dependsOn],
            doc_path: 'docs/requirements/' + changed.requirementId + '/tasks/' + changed.id + '.md',
          }
        : undefined
      return {
        success: true,
        task_id: changed.id,
        requirement_id: changed.requirementId,
        from,
        to: changed.status,
        ...(taskCard !== undefined ? { task_card: taskCard } : {}),
        requirement_status: reqAfter?.status ?? '',
        ...(blockers !== undefined
          ? { blockers, warning: '需求未进验收：' + blockers.length + ' 个任务未完成（' + blockers.map(b => b.id).join('、') + '）' }
          : {}),
        note: changed.status === to ? '已推进：' + from + ' → ' + to : '已推进：' + from + ' → ' + changed.status,
      }
    },
  } as any)
}

/**
 * reqboard_plan_submit —— 计划模式（plan mode）的提交口。
 *
 * 为什么需要它（用户要求「superpowers 的 plan 模式版本」）：拆分的闸门必须落在**计划**上，
 * 而不是落在"已拆分"这个状态上。窗口 agent 先把方案写成实施计划——一段人能读懂的摘要 +
 * 一份任务表（每项带 phase/side/依赖/验收标准）——提交到需求上；人批准后，decompose 只是
 * 把批准过的东西落库，不再二次创作。这样人只需要在**一个**点上把关，执行阶段仍然全自动。
 *
 * 重新提交 = 旧批准作废（必须重新批准）：改过方案的计划不能沿用上一轮的人点头。
 */
export function definePlanSubmitTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_plan_submit',
    description:
      '计划模式：把本窗口绑定需求的方案写成「实施计划」并提交给人批准——'
      + '拆分前必须先有计划且获批（未获批时 reqboard_decompose 会被代码级拒绝）。'
      + '计划 = 工作区里的计划文档路径 + 一段摘要 + 任务表（每项 key/title/phase/side/depends_on/acceptance）。'
      + '任务表就是将来要落库的任务卡，粒度在这里定死，人批准计划即批准拆分方案。'
      + '重新提交会作废旧批准，需要人重新批准。',
    parameters: {
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      path: { type: 'string', description: '计划文档路径（工作区相对路径，如 docs/requirements/REQ-xxxxxx/plan.md）', required: true },
      summary: { type: 'string', description: '计划摘要：目标 + 做法（人读这一段就能判断该不该批）', required: true },
      change_note: { type: 'string', description: '变更原因（REQ-2e9473 t19/W8）：计划已批准过再重交时**必填**——留痕并把下游标"待同步"' },
      tasks: {
        type: 'array',
        description: '任务表（可选，1-50 项）。W7：技术设计阶段可不交任务表（任务卡在拆分阶段创作）；交了则每项须含 implementation 与可证伪 acceptance',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            key: { type: 'string', description: '计划内引用键（如 t1；depends_on 用它引用）' },
            title: { type: 'string', description: '任务标题（动词开头，≤120 字符）' },
            description: { type: 'string', description: '任务说明（改哪些文件/接口）' },
            phase: { type: 'string', description: 'doc / ui / analysis / implement / test / review / merge' },
            side: { type: 'string', description: 'frontend / backend / fullstack / doc' },
            depends_on: { type: 'array', description: '依赖的计划内 key', items: { type: 'string' } },
            acceptance: { type: 'string', description: '验收标准（可验证：跑什么、看到什么算过；空话/缺锚点打回）' },
            implementation: { type: 'string', description: '实施方案（必填：改哪些文件、步骤、验证方式——拆分卡≠实施卡）' },
          },
        },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          plan_status: { type: 'string', description: 'pending_approval' },
          task_count: { type: 'number' },
          tasks: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                key: { type: 'string' },
                title: { type: 'string' },
                depends_on: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; path?: unknown; summary?: unknown; tasks?: unknown; change_note?: unknown }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const path = normalizeText(a.path, 'path', 400)
      const summary = normalizeText(a.summary, 'summary', 4000)
      const changeNote = normalizeText(a.change_note, 'change_note', 1000)
      if (path.length === 0) reject('reqboard_plan_submit 未执行：path 不能为空', 'REQBOARD_INVALID_INPUT')
      if (summary.length === 0) reject('reqboard_plan_submit 未执行：summary 不能为空（人要读它来决定批不批）', 'REQBOARD_INVALID_INPUT')
      // REQ-2e9473 t17/W7：任务表改可选——技术设计阶段只交一套设计文档（架构/四视角/风险/
      // 工作流划分），最终任务 DAG 由 decomposing 阶段创作。传了 tasks（旧习惯/预估划分）
      // 则仍走严格校验；不传则合法（tasks=[]）。
      const tasks = a.tasks === undefined ? [] : normalizePlanTasks(a.tasks)

      const snapshot = deps.store.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_plan_submit 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (target === undefined) {
        reject(
          'reqboard_plan_submit 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求',
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }
      // 流程纪律：计划属于「写计划」（planning）阶段。方案还没谈定就跳去写计划，正是流程要挡的越级。
      if (target.status !== 'planning') {
        reject(
          'reqboard_plan_submit 未执行：需求当前处于 ' + target.status + '，计划只能在 planning（写计划）阶段提交。'
          + '先把方案谈定 → reqboard_move 到 planning → 再提交计划；'
          + '已有计划要改，也先回到 planning 重新提交（旧批准自动作废）',
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
      const nowTs = deps.now()
      const result = await deps.store.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        if (prevPlanApproved) {
          // 计划变更 → 下游 decomposition 待同步 + changelog
          const downstream: string[] = []
          if ((req.artifacts ?? []).some(x => x.kind === 'decomposition')) downstream.push('decomposition')
          req.docSyncPending = [
            ...(req.docSyncPending ?? []).filter(p => p.source !== 'plan'),
            { source: 'plan', downstream, reason: changeNote, at: nowTs },
          ]
          req.comments.push({
            id: newCommentId(),
            body: '[文档变更] 技术设计（计划）变更：' + changeNote
              + '\n旧批准已作废（需重新批准）；下游待同步：' + (downstream.join('、') || '（暂无）'),
            createdAt: nowTs,
            createdBy: { kind: 'agent', sessionId: windowKey },
          })
        }
        // 销标：plan 重交即完成自身同步
        req.docSyncPending = (req.docSyncPending ?? []).filter(p => !p.downstream.includes('plan'))
        req.plan = {
          path,
          summary,
          tasks,
          submittedAt: nowTs,
          submittedBy: { kind: 'agent', sessionId: windowKey },
        }
        req.comments.push({
          id: newCommentId(),
          body:
            '[计划] 提交实施计划（' + tasks.length + ' 个任务，待人工批准）：' + path
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
      const changed = result.changed.requirements[0]
      if (changed === undefined) reject('reqboard_plan_submit 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // ── 产物登记（REQ-31e11f t4）：plan 产物 = 计划文档 ──────────────────
      const planArtifact: StageArtifact = {
        stage: 'planning',
        kind: 'plan',
        path,
        registeredAt: nowTs,
        registeredBy: { kind: 'agent', sessionId: windowKey },
      }
      await deps.store.mutate('requirement-updated', (ledger) => {
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
        task_count: tasks.length,
        tasks: tasks.map(t => ({ key: t.key, title: t.title, depends_on: [...(t.dependsOn ?? [])] })),
        note: '计划已提交' + (tasks.length === 0 ? '（技术设计，未含任务表——任务卡在拆分阶段创作）' : '（含 ' + tasks.length + ' 张预估任务卡）')
          + '。下一步：调 reqboard_ask_confirm（target=plan）弹框请人批准——批准后进拆分，用 reqboard_decompose 创作并落库任务卡（看板「批准计划」同样是有效通道）',
      }
    },
  } as any)
}

/**
 * 需求文档提交（brainstorming 阶段产物）—— REQ-ff20ca t1。
 *
 * 补上 5.0 记录的缺口：此前 registerArtifact 只在 decompose / plan_submit /
 * verify_submit / task_report 中被调用，**没有任何入口能登记 requirement 产物**，
 * 导致看板「确认需求文档」按钮 400（须先由工具登记）→ 五道门的第一道永远过不去。
 *
 * 与 reqboard_plan_submit 同构：内容校验（文件已落盘）→ 登记产物 → 通知请人审阅。
 */
export function defineRequirementSubmitTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_requirement_submit',
    description:
      '提交需求文档（brainstorming 阶段产物）：校验文档已落盘 → 登记 requirement 产物 → 发飞书通知请人审阅。'
      + '与 reqboard_plan_submit / reqboard_verify_submit 同构——人工确认门（brainstorming→planning）要求该产物已登记'
      + '且经人确认；未登记时看板确认按钮会被代码级拒绝。',
    parameters: {
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      path: { type: 'string', description: '需求文档路径（工作区相对路径）；不传默认 docs/requirements/<REQ>/requirement.md' },
      summary: { type: 'string', description: '一句话摘要（写入台账动态，供审阅者快速了解）' },
      change_note: { type: 'string', description: '变更原因（REQ-2e9473 t19/W8）：需求文档已确认过再重写时**必填**——留痕并把下游标"待同步"' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          artifact: {
            type: 'object',
            additionalProperties: false,
            properties: {
              stage: { type: 'string' },
              kind: { type: 'string' },
              path: { type: 'string' },
            },
          },
          registered: { type: 'boolean', description: 'false = 幂等命中（此前已登记，未重复登记）' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; path?: unknown; summary?: unknown; change_note?: unknown }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const explicitPath = normalizeText(a.path, 'path', 400)
      const summary = normalizeText(a.summary, 'summary', 2000)
      const changeNote = normalizeText(a.change_note, 'change_note', 1000)

      const snapshot = deps.store.snapshot()
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

      const path = explicitPath.length > 0 ? explicitPath : 'docs/requirements/' + target.id + '/requirement.md'
      const abs = join(process.cwd(), path)
      if (!existsSync(abs)) {
        reject(
          'reqboard_requirement_submit 未执行：文档不存在 ' + path + '（请先写出需求文档再提交）',
          'REQBOARD_FILE_MISSING',
        )
      }

      const nowTs = deps.now()
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
      const result = await deps.store.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        const added = registerArtifact(req, artifact)
        if (added) {
          req.comments.push({
            id: newCommentId(),
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
          const downstream: string[] = []
          if ((req.artifacts ?? []).some(x => x.kind === 'plan')) downstream.push('plan')
          if ((req.artifacts ?? []).some(x => x.kind === 'decomposition')) downstream.push('decomposition')
          req.docSyncPending = [
            ...(req.docSyncPending ?? []).filter(p => p.source !== 'requirement'),
            { source: 'requirement', downstream, reason: changeNote, at: nowTs },
          ]
          req.comments.push({
            id: newCommentId(),
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
      const changed = result.changed.requirements[0]
      if (changed === undefined) reject('reqboard_requirement_submit 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      const registered = !alreadyRegistered
      if (registered) notifyArtifactRegistered(deps, changed.id, artifact)
      return {
        success: true,
        requirement_id: changed.id,
        artifact: { stage: artifact.stage, kind: artifact.kind, path: artifact.path },
        registered,
        note: registered
          ? '需求文档产物已登记。下一步：调 reqboard_ask_confirm（target=artifact, kind=requirement）弹框请人确认——肯定答复自动落章并推进到 planning（看板一键确认同样是有效通道）'
          : '该需求文档此前已登记（幂等命中，未重复登记）',
      }
    },
  } as any)
}

/**
 * 会话确认落章（REQ-ff20ca t2）—— 把用户在 ask_user_question 中的明确确认，
 * 落成与看板一键确认**同等效力**的人工确认（五道人工确认门通用）。
 *
 * 审计不变量：evidence（用户答复原文）+ sessionId 必须落库——
 * agent 不能"自称已确认"而不留痕；确认来源（board/session）在台账里可查。
 */
export function defineConfirmArtifactTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_confirm_artifact',
    description:
      '会话确认落章：将用户在 ask_user_question 中的明确确认，落成与看板一键确认同等效力的人工确认。'
      + 'target=artifact 确认某产物（需 kind：requirement/plan/decomposition/verification/archive）；'
      + 'target=plan 批准实施计划（等价看板「批准计划」）。'
      + '必须附 evidence（用户在 ask_user_question 中的答复原文）——审计凭据，缺省即拒绝。',
    parameters: {
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      target: { type: 'string', description: 'artifact（确认产物）| plan（批准实施计划）', required: true },
      kind: { type: 'string', description: '产物类型（target=artifact 时必填）：requirement/plan/decomposition/verification/archive' },
      evidence: { type: 'string', description: '用户在 ask_user_question 中的确认答复原文（审计凭据，必填）', required: true },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          target: { type: 'string' },
          kind: { type: 'string' },
          via: { type: 'string' },
          evidence_verified: { type: 'boolean', description: '文字确认是否通过 capture-hook 核验（命中真实用户消息）' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
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
      if (deps.recentUserMsgs !== undefined) {
        const check = evidenceMatchesRecentUserMsg(deps.recentUserMsgs, windowKey, evidence, deps.now())
        if (!check.ok) {
          reject(
            'reqboard_confirm_artifact 未执行：文字确认核验失败——' + check.reason + '。'
            + '确认必须系统可见证：① 用 reqboard_ask_confirm 弹框（免引证）；'
            + '② evidence 引用用户最近真实消息原文；③ 用户看板一键确认',
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

      const snapshot = deps.store.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_confirm_artifact 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const targetReq = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (targetReq === undefined) {
        reject(
          'reqboard_confirm_artifact 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求',
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }

      const nowTs = deps.now()
      const result = await deps.store.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === targetReq.id)
        if (req === undefined) return undefined
        if (targetKind === 'artifact') {
          const art = (req.artifacts ?? []).find(x => x.kind === kindRaw)
          if (art === undefined) {
            reject(
              'reqboard_confirm_artifact 未执行：需求 ' + req.id + ' 没有 kind=' + kindRaw
              + ' 的产物（请先提交该阶段产物）',
              'REQBOARD_MISSING_ARTIFACT',
            )
          }
          art.confirmedAt = nowTs
          art.confirmedBy = { kind: 'human', sessionId: windowKey }
          art.confirmedVia = 'session'
          art.confirmedEvidence = evidence
          req.comments.push({
            id: newCommentId(),
            body:
              '[产物确认·会话] 人经 ask_user_question 确认产物（kind=' + kindRaw + '）：' + art.path
              + '\n答复原文：' + evidence,
            createdAt: nowTs,
            createdBy: { kind: 'human', sessionId: windowKey },
          })
        } else {
          if (req.plan === undefined) {
            reject('reqboard_confirm_artifact 未执行：需求 ' + req.id + ' 还没有实施计划', 'REQBOARD_MISSING_PLAN')
          }
          req.plan.approvedAt = nowTs
          req.plan.approvedBy = { kind: 'human', sessionId: windowKey }
          req.plan.approvedVia = 'session'
          req.plan.approvedEvidence = evidence
          delete req.plan.rejectedAt
          delete req.plan.rejectedReason
          req.comments.push({
            id: newCommentId(),
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
      const changed = result.changed.requirements[0]
      if (changed === undefined) reject('reqboard_confirm_artifact 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
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
    },
  } as any)
}

/**
 * reqboard_verify_submit —— 提交验收材料（人工审核的依据）。
 *
 * 用户要求「验收 有人工审核」：验收不是 agent 说"做完了"就算过——agent 把证据交上来
 * （做了什么、怎么验的、看到什么结果；可复核的命令/输出/路径），**人看着证据**点通过
 * 或退回返工。代码级：accepting>done 是人工闸门（本工具只能把人请到桌前，不能替他点头）。
 */
export function defineVerifySubmitTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_verify_submit',
    description:
      '提交验收材料（供人工审核）：summary=一句话交付结论（做了什么、验了什么），'
      + 'evidence=证据清单（可复核的命令与输出摘要 / 测试报告路径 / 截图路径，禁止"功能正常"这类空话）。'
      + '提交后需求进入/停在验收态，等人在项目看板人工审核：通过 → 完成；退回 → 返工（附意见）。'
      + '前置：需求属于本窗口，处于 implementing（实施）或 accepting（验收）阶段。',
    parameters: {
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      summary: { type: 'string', description: '交付结论（≤2000 字符）', required: true },
      evidence: {
        type: 'array',
        description: '证据清单（1-20 条；命令+结果摘要 / 报告路径 / 截图路径）',
        required: true,
        items: { type: 'string' },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          status: { type: 'string', description: '提交后的需求状态（accepting=待人工审核）' },
          tasks_done: { type: 'number' },
          tasks_total: { type: 'number' },
          sheet_version: { type: 'number', description: '验收单版本（v1/v2…）' },
          sheet_items: { type: 'number', description: '本轮验收项数' },
          rework_only: { type: 'boolean', description: '本轮是否只含上版未过项（返工续验）' },
          doc_sync_pending: {
            type: 'array',
            description: '待同步的下游文档（重交下游产物后销标）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                source: { type: 'string' },
                downstream: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          doc_sync_warning: { type: 'string' },
          warning: { type: 'string' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
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
      const missingPaths = citedPaths.filter(p => !existsSync(join(process.cwd(), p)))
      if (missingPaths.length > 0) {
        reject(
          'reqboard_verify_submit 未执行：evidence 引用的文件不存在（疑似编造）：'
          + missingPaths.join('、') + '。请引用真实存在的产物/报告路径，或改用命令+输出摘要',
          'REQBOARD_EVIDENCE_MISSING',
        )
      }

      const snapshot = deps.store.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_verify_submit 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (target === undefined) {
        reject('reqboard_verify_submit 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }
      if (target.status !== 'implementing' && target.status !== 'accepting') {
        reject('reqboard_verify_submit 未执行：需求处于 ' + target.status + '，只有执行/验收阶段的交付才能提交验收', 'REQBOARD_BAD_STATUS')
      }

      const nowTs = deps.now()
      const result = await deps.store.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        // ── 逐项验收单生成（REQ-2e9473 t13/W6）────────────────────────────
        // items = 每任务验收标准 + 需求级标准；返工时（上一版有未过项）只含未过项。
        const allTasks = ledger.tasks.filter(t => t.requirementId === req.id && t.status !== 'canceled')
        const prevSheet = req.verification?.sheet
        const prevFailed = (prevSheet?.items ?? []).filter(i => i.status === 'failed')
        const version = (req.verification?.sheetHistory?.length ?? 0) + (prevSheet !== undefined ? 1 : 0) + 1
        const reworkOnly = prevFailed.length > 0
        const items: VerificationItem[] = reworkOnly
          ? prevFailed.map((it, idx) => ({
              ...it,
              id: 'v' + version + '-' + (idx + 1),
              status: 'pending' as const,
              opinion: undefined,
              decidedAt: undefined,
              decidedBy: undefined,
            }))
          : [
              ...allTasks.map((t, idx) => ({
                id: 'v' + version + '-' + (idx + 1),
                source: t.id,
                criterion: t.acceptance.length > 0 ? t.acceptance : (t.title + '：交付完成'),
                evidence: [...evidence],
                status: 'pending' as const,
              })),
              {
                id: 'v' + version + '-' + (allTasks.length + 1),
                source: 'requirement',
                criterion: '需求级：交付结论可复核（证据齐全、与技术设计一致、无范围蔓延）',
                evidence: [...evidence],
                status: 'pending' as const,
              },
            ]
        const sheet: VerificationSheet = {
          version,
          items,
          generatedAt: nowTs,
          generatedBy: { kind: 'agent', sessionId: windowKey },
          ...(reworkOnly ? { reworkOnly: true } : {}),
        }
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
          id: newCommentId(),
          body: '[验收] 提交验收材料（待人工审核）：' + summary
            + '\n证据：\n' + evidence.map(e => '- ' + e).join('\n'),
          createdAt: nowTs,
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'agent', sessionId: windowKey }
        // 任务全完成时顺带推进到验收态（人来了就有东西可审）
        const advanced = applyTaskRollup(ledger, { now: nowTs, commentId: () => newCommentId() }, req.id)
        return { requirements: [req, ...advanced] }
      })
      const changed = result.changed.requirements[0]
      if (changed === undefined) reject('reqboard_verify_submit 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // ── 产物登记（REQ-31e11f t4）：verification 产物 ─────────────────────
      const verPath = 'docs/requirements/' + target.id + '/verification.md'
      const verAbs = join(process.cwd(), verPath)
      if (!existsSync(verAbs)) {
        mkdirSync(dirname(verAbs), { recursive: true })
        const verContent = [
          '# ' + target.id + ' 验收（verification）',
          '',
          '> 自动生成于 reqboard_verify_submit',
          '',
          '## 验收结论',
          summary,
          '',
          '## 证据清单',
          ...evidence.map(e => '- ' + e),
          '',
        ].join('\n')
        writeFileSync(verAbs, verContent, 'utf8')
      }
      await deps.store.mutate('requirement-updated', (ledger) => {
        const r = ledger.requirements.find(x => x.id === changed.id)
        if (r === undefined) return undefined
        registerArtifact(r, {
          stage: 'accepting', kind: 'verification', path: verPath,
          registeredAt: nowTs, registeredBy: { kind: 'agent', sessionId: windowKey },
        })
        return { requirements: [r] }
      })
      const ledgerNow = deps.store.snapshot()
      const tasks = ledgerNow.tasks.filter(t => t.requirementId === target.id && t.status !== 'canceled')
      const reqNow = ledgerNow.requirements.find(r => r.id === changed.id)
      // rollup 阻塞显式化（REQ-2e9473 t02）：有未完成任务时验收材料虽收，但需求进不了 accepting
      const blockers = reqNow === undefined ? undefined : rollupBlockersOf(ledgerNow, reqNow.id, reqNow.status)
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
          ? { doc_sync_pending: reqNow.docSyncPending, doc_sync_warning: '⏳ 文档待同步：' + (reqNow.docSyncPending ?? []).map(p => p.source + '→' + (p.downstream.join('/') || '-')).join('；') }
          : {}),
        ...(blockers !== undefined
          ? {
              blockers,
              warning: '⚠️ 需求未进验收（rollup 阻塞）：' + blockers.length + ' 个任务未完成——'
                + blockers.map(b => b.id + ' ' + b.title + '（' + b.status + '）').join('；')
                + '。若为重复拆分产生的幽灵任务，请人工取消后重新提交',
            }
          : {}),
        note: blockers !== undefined
          ? '验收材料已提交，但需求因 ' + blockers.length + ' 个未完成任务停在 implementing——见 warning/blockers'
          : '验收材料已提交。下一步：调 reqboard_ask_confirm（target=artifact, kind=verification）弹框请人逐项审核（看板「验收通过/退回」同样是有效通道）',
      }
    },
  } as any)
}

/**
 * reqboard_archive_submit —— 准备归档材料（归档的前置条件）。
 *
 * 用户要求「归档 要有项目文档设计，文档如何合并，不同问题如何记录文档」：归档 = 把这次
 * 需求的产出**并进项目文档**——需求目录留全套原始材料，同时把别人以后要读的那部分
 * 合并进 architecture / guides / known-issues / research / work-logs，并写一条索引条目。
 * 不同需求类型（feature/bug/doc/refactor/spike/chore）的必填文档与合并去向由
 * ARCHIVE_DOC_RULES 规定，本工具落库前逐条校验（代码级，不是提示词约定）。
 */
export function defineArchiveSubmitTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_archive_submit',
    description:
      '准备归档材料（人再点归档）：dir=需求目录（docs/requirements/REQ-xxxxxx），'
      + 'docs=目录内的文档清单（kind: requirement/plan/verification/retro/notes + path），'
      + 'merged_into=合并进的项目文档路径（按需求类型限定在 docs/adr|architecture|guides|rfcs|work-logs|strategy-research），'
      + 'index_entry=一句话结论（进归档索引）。不同需求类型的必填文档与合法去向见 '
      + 'agent-dh/docs/architecture/requirement-archive.md；缺项会被代码级拒绝。前置：需求已 done。',
    parameters: {
      requirement_id: { type: 'string', description: '需求 id；不传默认本窗口绑定的需求' },
      dir: { type: 'string', description: '需求目录（工作区相对路径）', required: true },
      docs: {
        type: 'array',
        description: '需求目录内的文档清单',
        required: true,
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            kind: { type: 'string', description: 'requirement / plan / verification / retro / notes' },
            path: { type: 'string', description: '文件路径（工作区相对路径）' },
          },
        },
      },
      merged_into: {
        type: 'array',
        description: '合并进的项目文档路径（1-10 条）',
        required: true,
        items: { type: 'string' },
      },
      index_entry: { type: 'string', description: '一句话结论（进归档索引）', required: true },
      manual_updates: {
        type: 'array',
        description: '项目说明书更新点（金字塔 L1/L2）：feature/refactor/spike 必填——'
          + '写清更新了哪一份文档的哪一节、多了什么认知',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            path: { type: 'string', description: '文档路径（如 docs/architecture/project-manual.md）' },
            section: { type: 'string', description: '章节标题' },
            summary: { type: 'string', description: '一句话：这一节现在多了什么认知' },
          },
        },
      },
      manual_note: { type: 'string', description: '无手册更新时的理由（bug/doc/chore 可只写这条）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          status: { type: 'string' },
          required_docs: { type: 'array', items: { type: 'string' } },
          unlisted_files: { type: 'array', items: { type: 'string' }, description: '目录内未列入归档清单的文件（W4 漏登警告）' },
          warning: { type: 'string', description: '漏登等非阻断警告' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as {
        requirement_id?: unknown
        dir?: unknown
        docs?: unknown
        merged_into?: unknown
        index_entry?: unknown
        manual_updates?: unknown
        manual_note?: unknown
      }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const dir = normalizeText(a.dir, 'dir', 400)
      const indexEntry = normalizeText(a.index_entry, 'index_entry', 1000)
      const kinds = ['requirement', 'plan', 'verification', 'retro', 'notes'] as const
      if (!Array.isArray(a.docs)) reject('reqboard_archive_submit 未执行：docs 必须是数组', 'REQBOARD_INVALID_INPUT')
      const docs = (a.docs as unknown[]).map(d => {
        const o = (typeof d === 'object' && d !== null ? d : {}) as Record<string, unknown>
        const path = normalizeText(o.path, 'docs[].path', 400)
        const rawKind = typeof o.kind === 'string' ? o.kind : ''
        const kind = (kinds as readonly string[]).includes(rawKind) ? (rawKind as (typeof kinds)[number]) : undefined
        if (kind === undefined) {
          reject('reqboard_archive_submit 未执行：docs[].kind 必须是 ' + kinds.join(' / '), 'REQBOARD_INVALID_INPUT')
        }
        if (path.length === 0) reject('reqboard_archive_submit 未执行：docs[].path 不能为空', 'REQBOARD_INVALID_INPUT')
        return { kind, path }
      })
      if (!Array.isArray(a.merged_into)) {
        reject('reqboard_archive_submit 未执行：merged_into 必须是数组', 'REQBOARD_INVALID_INPUT')
      }
      const mergedInto = (a.merged_into as unknown[])
        .map(m => normalizeText(m, 'merged_into[]', 400))
        .filter(m => m.length > 0)
        .slice(0, 10)
      const manualUpdates = Array.isArray(a.manual_updates)
        ? (a.manual_updates as unknown[]).map(u => {
          const o = (typeof u === 'object' && u !== null ? u : {}) as Record<string, unknown>
          return {
            path: normalizeText(o.path, 'manual_updates[].path', 400),
            section: normalizeText(o.section, 'manual_updates[].section', 200),
            summary: normalizeText(o.summary, 'manual_updates[].summary', 500),
          }
        })
        : []
      const manualNote = normalizeText(a.manual_note, 'manual_note', 500)

      // 归档的对象是**已完成**的需求——它已经不在 open 集合里，所以这里按「本窗口的需求」
      // （sourceSessionId 锚点）判定，而不是按 open 判定（否则归档永远找不到自己的需求）。
      const snapshot = deps.store.snapshot()
      const mine = snapshot.requirements.filter(r => r.sourceSessionId === windowKey)
      if (mine.length === 0) reject('reqboard_archive_submit 未执行：本窗口没有需求', 'REQBOARD_NO_BOUND_REQ')
      const target = explicitId.length > 0
        ? mine.find(r => r.id === explicitId)
        : [...mine].sort((a, b) => b.updatedAt - a.updatedAt)[0]
      if (target === undefined) {
        reject('reqboard_archive_submit 未执行：需求 ' + explicitId + ' 不是本窗口的需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }
      const actual = target
      // REQ-9f4a44：验收通过即 archived（归档自动化）——材料在 archived 下补齐；
      // `done` 为 legacy 兼容（历史需求仍可补材料，不被卡死）。
      if (actual.status !== 'archived' && actual.status !== 'done') {
        reject(
          'reqboard_archive_submit 未执行：需求处于 ' + actual.status
          + '，只有已归档（archived）或历史完成（done）的需求才能备归档材料',
          'REQBOARD_BAD_STATUS',
        )
      }
      try {
        assertArchiveMaterials(actual.category, {
          dir, docs, mergedInto, indexEntry,
          ...(manualUpdates.length > 0 ? { manualUpdates } : {}),
          ...(manualNote.length > 0 ? { manualNote } : {}),
        })
      } catch (err) {
        reject('reqboard_archive_submit 未执行：' + ((err as Error).message ?? String(err)), 'REQBOARD_INVALID_INPUT')
      }

      const nowTs = deps.now()
      const result = await deps.store.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === actual.id)
        if (req === undefined) return undefined
        req.archive = {
          dir, docs, mergedInto, indexEntry,
          ...(manualUpdates.length > 0 ? { manualUpdates } : {}),
          ...(manualNote.length > 0 ? { manualNote } : {}),
          submittedAt: nowTs,
          submittedBy: { kind: 'agent', sessionId: windowKey },
        }
        // REQ-9f4a44：材料补齐即归档收尾——写 archivePath（原"人点归档"承担的落章动作）
        if (req.status === 'archived') req.archivePath = dir
        req.comments.push({
          id: newCommentId(),
          body: '[归档] 材料已备（REQ-9f4a44：验收通过即自动归档，此步为材料补齐）：' + dir
            + '\n文档：' + docs.map(d => d.kind + '=' + d.path).join('；')
            + '\n合并进：' + mergedInto.join('；')
            + '\n索引：' + indexEntry
            + (manualUpdates.length > 0
              ? '\n说明书更新：' + manualUpdates.map(u => u.path + '#' + u.section + '（' + u.summary + '）').join('；')
              : (manualNote.length > 0 ? '\n说明书更新：无（' + manualNote + '）' : '')),
          createdAt: nowTs,
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'agent', sessionId: windowKey }
        return { requirements: [req] }
      })
      const changed = result.changed.requirements[0]
      if (changed === undefined) reject('reqboard_archive_submit 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // ── 产物登记（REQ-31e11f t4）：archive 产物 ───────────────────────────
      await deps.store.mutate('requirement-updated', (ledger) => {
        const r = ledger.requirements.find(x => x.id === changed.id)
        if (r === undefined) return undefined
        registerArtifact(r, {
          stage: 'done', kind: 'archive', path: dir,
          registeredAt: nowTs, registeredBy: { kind: 'agent', sessionId: windowKey },
        })
        return { requirements: [r] }
      })
      // 归档漏登警告（REQ-2e9473 t12/W4）：需求目录里存在但未列入归档清单的文件 → 提示，
      // 不硬拦（归档材料可能有意只收关键文档），但让漏登可见（事故 E 的归档侧变体）。
      const reqRootAbs = join(process.cwd(), 'docs/requirements', changed.id)
      const listedPaths = new Set(docs.map(d => d.path))
      const unlisted: string[] = []
      try {
        const { readdirSync: rd, statSync: st } = await import('node:fs')
        const walk = (absDir: string, rel: string): void => {
          for (const name of rd(absDir)) {
            if (name.startsWith('.')) continue
            const abs = join(absDir, name)
            const relPath = rel.length > 0 ? rel + '/' + name : name
            const s = st(abs)
            if (s.isDirectory()) { walk(abs, relPath); continue }
            const workspacePath = 'docs/requirements/' + changed.id + '/' + relPath
            if (!listedPaths.has(workspacePath) && !listedPaths.has(relPath)) unlisted.push(workspacePath)
          }
        }
        walk(reqRootAbs, '')
      } catch { /* 目录不存在 → 无漏登可查 */ }
      return {
        success: true,
        requirement_id: changed.id,
        status: changed.status,
        required_docs: [...(ARCHIVE_DOC_RULES[actual.category ?? 'feature'].requiredDocs)],
        ...(unlisted.length > 0
          ? { unlisted_files: unlisted, warning: '⚠️ 需求目录内有 ' + unlisted.length + ' 个文件未列入归档清单：' + unlisted.slice(0, 8).join('、') + (unlisted.length > 8 ? ' 等' : '') }
          : {}),
        note: '归档材料已备齐并登记（ACCEPT→ARCHIVED 已自动完成，无需人工点归档）'
          + (unlisted.length > 0 ? '；另有 ' + unlisted.length + ' 个目录内文件未列入清单（见 warning/unlisted_files）' : ''),
      }
    },
  } as any)
}

/**
 * reqboard_task_report —— 任务完成汇报（实施产物登记口）。
 *
 * 为什么需要它（REQ-31e11f t3，「节点完成=节点产物就位」）：实施节点的必备产物是
 * task_detail（每任务一份 tasks/t-xxx.md，见 STAGE_ARTIFACT_REQUIREMENTS.implementing）。
 * 任务卡文档是**双角色**：decompose 落库时生成骨架（开工说明书），本工具把 agent 的
 * 结构化汇报（completed / files_changed / next_step）渲染成 Markdown **追加**到同一
 * 文档——完工记录与开工说明同址，节点面板沿产物链一次点开即见全程。
 *
 * 行为：
 *   1. 校验任务存在且属于本窗口绑定的需求（与 task_move 同款越权校验，防替他窗口
 *      任务登记产物）；
 *   2. 渲染汇报段（时间戳 + 窗口 + summary + 完成项/改动文件/下一步）追加到
 *      docs/requirements/<REQ>/tasks/<task_id>.md；文件不存在则先写骨架头
 *      （任务标题 + 验收标准，对应 StageTaskRef.acceptance）；
 *   3. 向 req.artifacts 登记一条 kind='task_detail' / stage='implementing' 的
 *      StageArtifact（registeredBy=agent）；幂等——同 task_id 重复汇报只追加段落，
 *      不重复登记 artifact（按 path 去重）；
 *   4. 任务卡上留一条评论（[任务汇报] 前缀），供时间线/复盘检索。
 *
 * 写盘用 node:fs 同步 API + mkdirSync recursive：tasks/ 子目录在旧需求里可能不存在，
 * 递归创建保证任意层级都能落盘。路径以工作区根（process.cwd()）为基准拼接。
 */
export function defineTaskReportTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_task_report',
    description:
      '任务完成汇报：把"做了什么"结构化落到任务卡文档（docs/requirements/<REQ>/tasks/<task_id>.md），'
      + '并登记实施节点产物（kind=task_detail）。任务卡文档双角色：开工说明书（decompose 生成骨架）'
      + '+ 完工记录（本工具追加汇报）。参数：task_id=任务 id；summary=一句话做了什么；'
      + 'completed=完成项列表；files_changed=改动文件列表；next_step=下一步。'
      + '重复汇报幂等：追加新段落但不重复登记产物。'
      + '前置：任务属于本窗口绑定的需求。',
    parameters: {
      task_id: { type: 'string', description: '任务 id（t-xxxxxx）', required: true },
      summary: { type: 'string', description: '一句话汇报：做了什么（≤2000 字符）', required: true },
      completed: {
        type: 'array',
        description: '完成项列表（1-50 条）',
        items: { type: 'string' },
      },
      files_changed: {
        type: 'array',
        description: '改动文件列表（工作区相对路径，0-50 条）',
        items: { type: 'string' },
      },
      next_step: { type: 'string', description: '下一步（≤1000 字符；无则空串）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          requirement_id: { type: 'string' },
          doc_path: { type: 'string', description: '任务卡文档路径（工作区相对）' },
          artifact_registered: { type: 'boolean', description: '本次是否新登记产物（false=已存在，幂等跳过重登）' },
          report_index: { type: 'number', description: '本次汇报是第几段（从 1 起）' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as {
        task_id?: unknown
        summary?: unknown
        completed?: unknown
        files_changed?: unknown
        next_step?: unknown
      }
      const taskId = normalizeText(a.task_id, 'task_id', 64)
      if (taskId.length === 0) reject('reqboard_task_report 未执行：task_id 不能为空', 'REQBOARD_INVALID_INPUT')
      const summary = normalizeText(a.summary, 'summary', 2000)
      if (summary.length === 0) reject('reqboard_task_report 未执行：summary 不能为空', 'REQBOARD_INVALID_INPUT')
      const completed = Array.isArray(a.completed)
        ? (a.completed as unknown[]).map(c => normalizeText(c, 'completed[]', 500)).filter(c => c.length > 0).slice(0, 50)
        : []
      const filesChanged = Array.isArray(a.files_changed)
        ? (a.files_changed as unknown[]).map(f => normalizeText(f, 'files_changed[]', 400)).filter(f => f.length > 0).slice(0, 50)
        : []
      const nextStep = normalizeText(a.next_step, 'next_step', 1000)

      // ── 越权校验（与 task_move 同款）：任务必须属于本窗口绑定的需求 ──────────
      const snapshot = deps.store.snapshot()
      const task = snapshot.tasks.find(t => t.id === taskId)
      if (task === undefined) {
        reject('reqboard_task_report 未执行：任务 ' + taskId + ' 不存在', 'REQBOARD_TASK_NOT_FOUND')
      }
      const bound = openRequirementsFor(snapshot, windowKey)
      if (!bound.some(r => r.id === task.requirementId)) {
        reject(
          'reqboard_task_report 未执行：任务 ' + taskId + ' 不属于本窗口绑定的需求',
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }
      const req = snapshot.requirements.find(r => r.id === task.requirementId)
      if (req === undefined) {
        reject('reqboard_task_report 未执行：需求 ' + task.requirementId + ' 不在台账中', 'REQBOARD_STORE_INCONSISTENT')
      }


      // ── 渲染汇报段并追加落盘（文件不存在则先写任务卡骨架头）────────────────
      const docRel = 'docs/requirements/' + req.id + '/tasks/' + task.id + '.md'
      const docAbs = join(process.cwd(), docRel)
      const nowTs = deps.now()
      const when = new Date(nowTs).toISOString()

      // 骨架头：任务标题 + 验收标准（对应 StageTaskRef.acceptance；开工说明书角色）
      if (!existsSync(docAbs)) {
        const header = [
          '# ' + task.id + ' ' + task.title,
          '',
          '> 需求：' + req.id + ' ' + req.title,
          '> 验收标准：' + (task.acceptance.length > 0 ? task.acceptance : '（未填写）'),
          '',
          '---',
          '',
        ].join('\n')
        mkdirSync(dirname(docAbs), { recursive: true })
        writeFileSync(docAbs, header, 'utf8')
      }

      // 数已有汇报段数（用于 report_index；幂等语义：每次追加都是新一段）
      const existing = readFileSync(docAbs, 'utf8')
      const reportIndex = (existing.match(/^## 汇报 /gm) ?? []).length + 1

      const section = [
        '## 汇报 ' + reportIndex + '（' + when + '，窗口 ' + windowKey + '）',
        '',
        summary,
        '',
        ...(completed.length > 0
          ? ['### 完成项', '', ...completed.map(c => '- ' + c), '']
          : []),
        ...(filesChanged.length > 0
          ? ['### 改动文件', '', ...filesChanged.map(f => '- `' + f + '`'), '']
          : []),
        ...(nextStep.length > 0 ? ['### 下一步', '', nextStep, ''] : []),
        '---',
        '',
      ].join('\n')
      appendFileSync(docAbs, section, 'utf8')

      // ── 登记产物（幂等：同 path 不重复登记）──────────────────────────────
      const artifact: StageArtifact = {
        stage: 'implementing',
        kind: 'task_detail',
        path: docRel,
        registeredAt: nowTs,
        registeredBy: { kind: 'agent', sessionId: windowKey },
      }
      const result = await deps.store.mutate('requirement-updated', (ledger) => {
        const r = ledger.requirements.find(x => x.id === req.id)
        if (r === undefined) return undefined
        // done 凭证门证据源（REQ-2e9473 t06）：汇报即结构化留痕到任务记录
        const tk = ledger.tasks.find(x => x.id === task.id)
        if (tk !== undefined) {
          tk.lastReport = { at: nowTs, reportIndex, filesChanged: [...filesChanged], completed: [...completed] }
          tk.version += 1
          tk.updatedAt = nowTs
        }
        r.artifacts ??= []
        const already = r.artifacts.some(x => x.path === artifact.path && x.kind === artifact.kind)
        if (!already) r.artifacts.push(artifact)
        // 任务文件上浮（REQ-2e9473 t12/W4）：汇报的改动文件自动登记到需求级产物清单，
        // 覆盖 REQ 目录之外的源码文件——需求详情页可见"这个需求一共动了哪些文件"。
        for (const f of filesChanged) {
          if (r.artifacts.some(x => x.path === f && x.kind === 'task_output')) continue
          r.artifacts.push({
            stage: 'implementing',
            kind: 'task_output',
            path: f,
            registeredAt: nowTs,
            registeredBy: { kind: 'agent', sessionId: windowKey },
          } as StageArtifact)
        }
        r.comments.push({
          id: newCommentId(),
          body: '[任务汇报] ' + task.id + ' ' + task.title + '：' + summary
            + '\n产物：' + docRel
            + (filesChanged.length > 0 ? '\n改动：' + filesChanged.join('、') : '')
            + '\n（窗口 ' + windowKey + '）',
          createdAt: nowTs,
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        r.version += 1
        r.updatedAt = nowTs
        r.updatedBy = { kind: 'agent', sessionId: windowKey }
        return { requirements: [r], ...(tk !== undefined ? { tasks: [tk] } : {}) }
      })
      const changed = result.changed.requirements[0]
      if (changed === undefined) reject('reqboard_task_report 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // 产物已登记 = 同 path 的 artifact 存在（不管是本次登记还是 decompose 时已登记）
      const artifactRegistered = changed.artifacts?.some(x => x.path === artifact.path) ?? false

      return {
        success: true,
        task_id: task.id,
        requirement_id: req.id,
        doc_path: docRel,
        artifact_registered: artifactRegistered,
        report_index: reportIndex,
        note: '汇报已追加到 ' + docRel + '（第 ' + reportIndex + ' 段）'
          + (artifactRegistered ? '，产物已登记' : '，产物已存在（幂等跳过重登）'),
      }
    },
  } as any)
}

/**
 * reqboard_ask_confirm —— 关键确认弹框原子工具（REQ-2e9473 t07/W1，事故 A 修复）。
 *
 * 一次调用完成「弹框 → 落章 → 推进」：
 *   1. 经 ctx.userQuestions 服务接缝弹框（与 ask_user_question 同一 UI 通道）；
 *   2. 用户选肯定项 → 自动落章（via=session，evidence=答复原文）；
 *   3. advance=true（默认）→ 自动推进到下一阶段（限 brainstorming→planning /
 *      planning→decomposing / decomposing→implementing；验收通过属验收单流程不在此列）。
 *
 * 设计动机（REQ-6f39b5 事故 A）：ask_user_question 的答复是惰性数据，落章+推进全靠
 * agent 自觉串链——漏一步用户就"点了没推进"。原子化后漏步在结构上不可能。
 *
 * 降级：userQuestions 服务缺失或调用方是 subagent（DELEGATED_CALLER/CALLER_NOT_LIVE）
 * → 不报错，返回 fallback='board' 提示用户走看板确认按钮（三通道确认原则：永不死锁）。
 */
export function defineAskConfirmTool(deps: ReqboardToolDeps) {
  /** 允许 ask_confirm 自动推进的转移（验收通过与归档不由本工具代办）。 */
  const ADVANCE_MAP: Readonly<Record<string, string>> = {
    brainstorming: 'planning',
    planning: 'decomposing',
    decomposing: 'implementing',
  }
  return defineTool({
    name: 'reqboard_ask_confirm',
    description:
      '关键确认弹框（原子化：弹框 → 落章 → 推进一次完成）。'
      + '适用：阶段产物确认（target=artifact, kind=requirement/decomposition/verification/archive）、'
      + '批准实施计划（target=plan）。用户选肯定项 → 自动落章并推进到下一阶段；'
      + '选"需修改/暂停" → 不推进并留痕。subagent/无 UI 通道时返回 fallback=board（请用户走看板确认按钮）。',
    parameters: {
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      target: { type: 'string', description: 'artifact（确认产物）| plan（批准实施计划）', required: true },
      kind: { type: 'string', description: '产物类型（target=artifact 时必填）：requirement/plan/decomposition/verification/archive' },
      question: { type: 'string', description: '弹框问题（写清确认什么、确认后会发生什么）', required: true },
      options: {
        type: 'array',
        description: '选项标签列表（第一个 = 肯定项，确认后落章+推进；缺省：确认推进/需要修改/暂停）',
        items: { type: 'string' },
      },
      advance: { type: 'boolean', description: '确认后是否自动推进到下一阶段（默认 true）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          confirmed: { type: 'boolean' },
          advanced: { type: 'boolean' },
          from: { type: 'string' },
          to: { type: 'string' },
          requirement_id: { type: 'string', description: '被确认的需求 id' },
          fallback: { type: 'string', description: 'board = 弹框不可用，请走看板确认按钮' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 600000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as {
        requirement_id?: unknown; target?: unknown; kind?: unknown
        question?: unknown; options?: unknown; advance?: unknown
      }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const targetKind = normalizeText(a.target, 'target', 32)
      const kindRaw = normalizeText(a.kind, 'kind', 64)
      const question = normalizeText(a.question, 'question', 2000)
      const options = Array.isArray(a.options)
        ? (a.options as unknown[]).map(o => normalizeText(o, 'options[]', 200)).filter(o => o.length > 0).slice(0, 5)
        : []
      const advance = a.advance !== false
      if (question.length === 0) reject('reqboard_ask_confirm 未执行：question 不能为空', 'REQBOARD_INVALID_INPUT')
      if (targetKind !== 'artifact' && targetKind !== 'plan') {
        reject('reqboard_ask_confirm 未执行：target 只能是 artifact 或 plan', 'REQBOARD_INVALID_INPUT')
      }
      if (targetKind === 'artifact' && !(ALL_ARTIFACT_KINDS as readonly string[]).includes(kindRaw)) {
        reject('reqboard_ask_confirm 未执行：kind 必须是 ' + ALL_ARTIFACT_KINDS.join(' / '), 'REQBOARD_INVALID_INPUT')
      }
      const optionLabels = options.length > 0 ? options : ['确认，推进到下一阶段 (Recommended)', '需要修改', '暂停']

      const snapshot = deps.store.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_ask_confirm 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const targetReq = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (targetReq === undefined) {
        reject('reqboard_ask_confirm 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }

      // ── 弹框（userQuestions 服务接缝）────────────────────────────────────
      const svc = deps.userQuestions?.() as { ask?: (req: unknown) => Promise<{ answers?: { id?: string; selected?: string[]; custom?: string }[] }> } | undefined
      if (typeof svc?.ask !== 'function') {
        return {
          success: false, confirmed: false, advanced: false, fallback: 'board',
          note: '弹框通道不可用（userQuestions 服务缺失）：请用户到项目看板点确认按钮；或由 agent 改用 ask_user_question + reqboard_confirm_artifact 两步走',
        } as never
      }
      let answers: { id?: string; selected?: string[]; custom?: string }[] = []
      try {
        const result = await svc.ask({
          questions: [{
            id: 'confirm',
            question,
            header: '确认',
            options: optionLabels.map((label, i) => ({ label, ...(i === 0 ? { description: '确认后自动落章并推进' } : {}) })),
          }],
          ...(exec.agent !== undefined ? { agent: exec.agent } : {}),
          signal: (exec as { signal?: unknown }).signal,
        })
        answers = result.answers ?? []
      } catch (err) {
        const code = (err as { code?: string }).code ?? ''
        if (code === 'DELEGATED_CALLER' || code === 'CALLER_NOT_LIVE') {
          return {
            success: false, confirmed: false, advanced: false, fallback: 'board',
            note: '当前调用方无弹框权限（subagent/非活窗口）：请用户到项目看板点确认按钮完成本次确认',
          } as never
        }
        // ASK_ABORTED 等：用户暂离/取消——中性返回，不算错误
        return {
          success: false, confirmed: false, advanced: false,
          note: '用户未作答（取消/暂离）：节点未推进。稍后可重新发起 reqboard_ask_confirm',
        } as never
      }

      const answer = answers[0]
      const picked = answer?.selected?.[0] ?? answer?.custom ?? ''
      const affirmative = picked.length > 0 && picked === optionLabels[0]
      const nowTs = deps.now()

      // ── 非肯定项：不推进，留痕 ──────────────────────────────────────────
      if (!affirmative) {
        await deps.store.mutate('requirement-updated', (ledger) => {
          const req = ledger.requirements.find(r => r.id === targetReq.id)
          if (req === undefined) return undefined
          req.comments.push({
            id: newCommentId(),
            body: '[确认弹框] 用户未确认（选择：' + (picked || '（未选）') + '）——节点未推进。问题：' + question,
            createdAt: nowTs,
            createdBy: { kind: 'human', sessionId: windowKey },
          })
          req.version += 1
          req.updatedAt = nowTs
          return { requirements: [req] }
        })
        return {
          success: true, confirmed: false, advanced: false,
          note: '用户选择"' + (picked || '（未选）') + '"：未落章、未推进。按用户意见修改后可重新发起确认',
        } as never
      }

      // ── 肯定项：落章（与 reqboard_confirm_artifact 同语义）────────────────
      const evidence = '用户在 reqboard_ask_confirm 弹框（问题："' + question + '"）中选择"' + picked + '"'
      const confirmResult = await deps.store.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === targetReq.id)
        if (req === undefined) return undefined
        if (targetKind === 'artifact') {
          const art = (req.artifacts ?? []).find(x => x.kind === kindRaw)
          if (art === undefined) {
            throw Object.assign(
              new Error('需求 ' + req.id + ' 没有 kind=' + kindRaw + ' 的产物（请先提交该阶段产物）'),
              { code: 'REQBOARD_MISSING_ARTIFACT' },
            )
          }
          art.confirmedAt = nowTs
          art.confirmedBy = { kind: 'human', sessionId: windowKey }
          art.confirmedVia = 'session'
          art.confirmedEvidence = evidence
        } else {
          if (req.plan === undefined) {
            throw Object.assign(new Error('需求 ' + req.id + ' 还没有实施计划'), { code: 'REQBOARD_MISSING_PLAN' })
          }
          req.plan.approvedAt = nowTs
          req.plan.approvedBy = { kind: 'human', sessionId: windowKey }
          req.plan.approvedVia = 'session'
          req.plan.approvedEvidence = evidence
          delete req.plan.rejectedAt
          delete req.plan.rejectedReason
        }
        req.comments.push({
          id: newCommentId(),
          body: '[确认弹框] 用户确认（' + (targetKind === 'artifact' ? 'kind=' + kindRaw : '批准计划') + '）：' + evidence,
          createdAt: nowTs,
          createdBy: { kind: 'human', sessionId: windowKey },
        })
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'human', sessionId: windowKey }
        return { requirements: [req] }
      }).catch((err: unknown) => {
        reject('reqboard_ask_confirm 落章失败：' + ((err as Error).message ?? String(err)), (err as { code?: string }).code ?? 'REQBOARD_STORE_INCONSISTENT')
      })

      // ── 推进（可选，限白名单转移）───────────────────────────────────────
      const from = targetReq.status
      const to = ADVANCE_MAP[from]
      let advanced = false
      let advanceNote = ''
      if (advance && to !== undefined && canReqTransition(from, to as never)) {
        try {
          await deps.store.mutate('requirement-moved', (ledger) => {
            const req = ledger.requirements.find(r => r.id === targetReq.id)
            if (req === undefined || req.status !== from) return undefined
            req.status = to as never
            req.version += 1
            req.updatedAt = nowTs
            req.updatedBy = { kind: 'system' }
            recordStatus(req, to as never, nowTs, { kind: 'human', sessionId: windowKey }, '确认弹框后自动推进（reqboard_ask_confirm）')
            req.comments.push({
              id: newCommentId(),
              body: '[自动推进] ' + from + ' → ' + to + '：确认弹框肯定答复（reqboard_ask_confirm 原子推进）',
              createdAt: nowTs,
              createdBy: { kind: 'human', sessionId: windowKey },
            })
            return { requirements: [req] }
          })
          advanced = true
        } catch (err) {
          advanceNote = '；推进失败：' + ((err as Error).message ?? String(err))
        }
      } else if (advance) {
        advanceNote = '；当前状态 ' + from + ' 无可自动推进的下一阶段（验收/归档走验收单流程）'
      }

      return {
        success: true,
        confirmed: true,
        advanced,
        from,
        to: advanced ? to : from,
        requirement_id: targetReq.id,
        note: '已落章（via=session）' + (advanced ? '，已推进：' + from + ' → ' + to : '') + advanceNote,
      } as never
    },
  } as any)
}


/**
 * reqboard_accept_sheet —— 验收单逐项弹框验收（REQ-2e9473 W6 补口，用户要求）
 *
 * 为什么需要它：W6 验收单要求"人逐项打勾"，看板勾选是并行通道；而会话里此前
 * **没有记录弹框答复的路径**（confirm_artifact 只做单点落章）。本工具把
 * 「逐项弹框 → 直接落库裁决（系统见证，无需 agent 转述）→ 未过项自动返工」原子化：
 *   - 每次弹一批（默认 5 项，≤10），选项：✅ 通过 / 🛠 改进（需修改）/ ❓ 其他；
 *   - 选"改进/其他"需在自定义输入里写意见（否则以选项名作为意见兜底）；
 *   - 有不通过项 → 需求打回 implementing + 自动生成关联返工任务（复用 host/verdicts）；
 *   - 仍有待验项 → 挂起，再次调用本工具从断点继续（只弹未验项）。
 *
 * 降级：userQuestions 服务缺失 / subagent 调用 → 返回 fallback='board'（看板勾选）。
 */
export function defineAcceptSheetTool(deps: ReqboardToolDeps) {
  return defineTool({
    name: 'reqboard_accept_sheet',
    description:
      '验收单逐项弹框验收（原子：弹框 → 记录裁决 → 未过项自动返工）。'
      + '每次弹一批待验项（batch_size 默认 5，≤10），选项 通过/改进/其他；'
      + '选"改进/其他"请写意见（自定义输入）。仍有待验项时再次调用本工具从断点继续。'
      + 'subagent/无 UI 通道时返回 fallback=board（请用户走看板勾选）。',
    parameters: {
      requirement_id: { type: 'string', description: '需求 id；不传默认本窗口绑定的需求' },
      batch_size: { type: 'number', description: '本批弹出的最大项数（默认 5，上限 10）' },
      version: { type: 'number', description: '验收单版本（不传取当前 sheet 版本）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          sheet_version: { type: 'number' },
          recorded: { type: 'number', description: '本批记录的裁决数' },
          pending: { type: 'number', description: '剩余待验项数（挂起继续）' },
          passed: { type: 'number' },
          failed: { type: 'number' },
          rework_tasks: { type: 'array', items: { type: 'string' } },
          archived: { type: 'boolean', description: 'true = 全通过并已验收通过归档' },
          status: { type: 'string', description: '确认后的需求状态（archived 等）' },
          fallback: { type: 'string', description: 'board = 弹框不可用，请走看板勾选' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 900000,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const windowKey = agentIdFromExec(exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; batch_size?: unknown; version?: unknown }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const batchSize = Math.min(Math.max(Number(a.batch_size ?? 5) || 5, 1), 10)

      const snapshot = deps.store.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_accept_sheet 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const targetReq = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (targetReq === undefined) {
        reject('reqboard_accept_sheet 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }
      const sheet = targetReq.verification?.sheet
      if (sheet === undefined) reject('reqboard_accept_sheet 未执行：该需求还没有验收单（先 reqboard_verify_submit）', 'REQBOARD_NO_SHEET')
      if (a.version !== undefined && Number(a.version) !== sheet.version) {
        reject('reqboard_accept_sheet 未执行：验收单版本不匹配（当前 v' + sheet.version + '）', 'REQBOARD_VERSION_MISMATCH')
      }
      const svc = deps.userQuestions?.() as { ask?: (req: unknown) => Promise<{ answers?: { id?: string; selected?: string[]; custom?: string }[] }> } | undefined

      /**
       * 全部通过 → 直接弹「验收通过并归档」确认（REQ-2e9473 W6 闭环，用户指出）：
       * 逐项全过后不再要求人去点看板——同一次会话里接着弹最终确认，确认即归档。
       */
      const finalizeIfAllPassed = async (passed: number, failed: number): Promise<Record<string, unknown> | undefined> => {
        if (failed > 0) return undefined
        const cur = deps.store.snapshot().requirements.find(r => r.id === targetReq.id)
        if (cur === undefined || cur.status !== 'accepting') return undefined
        const curSheet = cur.verification?.sheet
        if (curSheet !== undefined && curSheet.items.some(i => i.status !== 'passed')) return undefined
        if (typeof svc?.ask !== 'function') {
          return { success: false, fallback: 'board', note: '全部 ' + passed + ' 项通过，但弹框通道不可用：请在看板点「验收通过」归档' }
        }
        const FINAL_YES = '✅ 验收通过并归档'
        let ans: { answers?: { id?: string; selected?: string[] }[] } | undefined
        try {
          ans = await svc.ask({
            questions: [{
              id: 'final-pass',
              header: '验收通过',
              question: '全部 ' + passed + ' 项验收通过——是否验收通过并归档？',
              options: [
                { label: FINAL_YES, description: '需求进入归档态，随后补归档材料' },
                { label: '暂不归档', description: '保持验收态，稍后再定' },
              ],
            }],
            ...(exec.agent !== undefined ? { agent: exec.agent } : {}),
            signal: (exec as { signal?: unknown }).signal,
          })
        } catch (err) {
          const code = (err as { code?: string }).code ?? ''
          if (code === 'DELEGATED_CALLER' || code === 'CALLER_NOT_LIVE') {
            return { success: false, fallback: 'board', note: '全部通过，但当前调用方无弹框权限：请在看板点「验收通过」' }
          }
          return { success: false, passed, failed: 0, note: '用户未作答最终确认：需求保持验收态（可重新调用本工具或看板确认）' }
        }
        if ((ans?.answers?.[0]?.selected?.[0] ?? '') !== FINAL_YES) {
          return { success: true, recorded: 0, pending: 0, passed, failed: 0, note: '用户选择暂不归档：需求保持验收态' }
        }
        const nowTs2 = deps.now()
        const moved = await deps.store.mutate('requirement-moved', (ledger) => {
          const r = ledger.requirements.find(x => x.id === targetReq.id)
          if (r === undefined) return undefined
          if (r.status !== 'accepting') {
            throw Object.assign(new Error('需求当前处于 ' + r.status + '，不在验收态'), { code: 'bad_status' })
          }
          const v = r.verification
          if (v !== undefined) {
            v.reviewedAt = nowTs2
            v.reviewedBy = { kind: 'human', sessionId: windowKey }
            v.decision = 'pass'
          }
          r.status = 'archived'
          r.version += 1
          r.updatedAt = nowTs2
          r.updatedBy = { kind: 'human', sessionId: windowKey }
          recordStatus(r, 'archived', nowTs2, { kind: 'human', sessionId: windowKey }, '验收通过（弹框逐项全通过 → 会话确认）')
          r.comments.push({
            id: newCommentId(),
            body: '[验收] 人工审核通过（弹框确认，' + passed + ' 项全通过）→ 自动归档',
            createdAt: nowTs2,
            createdBy: { kind: 'human', sessionId: windowKey },
          })
          return { requirements: [r] }
        }).catch((err: unknown) => {
          reject('reqboard_accept_sheet 归档失败：' + ((err as Error).message ?? String(err)), (err as { code?: string }).code ?? 'REQBOARD_STORE_INCONSISTENT')
        })
        const movedReq = moved.changed.requirements[0]
        return {
          success: true, recorded: 0, pending: 0, passed, failed: 0,
          archived: true, status: movedReq?.status ?? 'archived',
          note: '✅ 验收通过 → 已归档：请调 reqboard_archive_submit 补归档材料（目录/清单/合并去向/索引）',
        }
      }

      const pendingItems = sheet.items.filter(i => i.status === 'pending').slice(0, batchSize)
      if (pendingItems.length === 0) {
        const passedN = sheet.items.filter(i => i.status === 'passed').length
        const failedN = sheet.items.filter(i => i.status === 'failed').length
        const fin = await finalizeIfAllPassed(passedN, failedN)
        if (fin !== undefined) return fin as never
        return {
          success: true, requirement_id: targetReq.id, sheet_version: sheet.version,
          recorded: 0, pending: 0, passed: passedN, failed: failedN,
          note: failedN > 0 ? '有未过项：需求已打回返工（修复后重交验收单，v2 只验未过项）' : '全部已裁决（等待验收通过）',
        } as never
      }

      if (typeof svc?.ask !== 'function') {
        return {
          success: false, fallback: 'board',
          note: '弹框通道不可用（userQuestions 服务缺失）：请用户到项目看板验收面板逐项勾选（看板通道等效）',
        } as never
      }
      const OPT_PASS = '✅ 通过'
      const OPT_FIX = '🛠 改进（需修改）'
      const OPT_OTHER = '❓ 其他'
      let answers: { id?: string; selected?: string[]; custom?: string }[] = []
      try {
        const result = await svc.ask({
          questions: pendingItems.map(it => ({
            id: it.id,
            header: it.source === 'requirement' ? '需求级验收' : ('验收项 ' + it.source),
            question: it.criterion + (it.evidence.length > 0 ? '\n（证据：' + it.evidence.slice(0, 2).join('；') + '）' : ''),
            options: [
              { label: OPT_PASS, description: '该验收项通过' },
              { label: OPT_FIX, description: '需修改——请在自定义输入写意见' },
              { label: OPT_OTHER, description: '其他结论——请在自定义输入说明' },
            ],
          })),
          ...(exec.agent !== undefined ? { agent: exec.agent } : {}),
          signal: (exec as { signal?: unknown }).signal,
        })
        answers = result.answers ?? []
      } catch (err) {
        const code = (err as { code?: string }).code ?? ''
        if (code === 'DELEGATED_CALLER' || code === 'CALLER_NOT_LIVE') {
          return { success: false, fallback: 'board', note: '当前调用方无弹框权限：请用户到项目看板验收面板逐项勾选' } as never
        }
        return { success: false, note: '用户未作答（取消/暂离）：未记录任何裁决，稍后可重新调用' } as never
      }

      const byId = new Map(answers.map(ans => [ans.id ?? '', ans]))
      const verdicts: { itemId: string; status: 'passed' | 'failed'; opinion?: string }[] = []
      for (const it of pendingItems) {
        const ans = byId.get(it.id)
        if (ans === undefined) continue // 未作答 → 保持 pending（挂起点）
        const picked = ans.selected?.[0] ?? ''
        const custom = (ans.custom ?? '').trim()
        if (picked === OPT_PASS) {
          verdicts.push({ itemId: it.id, status: 'passed' })
        } else {
          const opinion = custom.length > 0 ? custom : (picked.replace(/^[^\w\u4e00-\u9fa5]+/, '') || '需修改')
          verdicts.push({ itemId: it.id, status: 'failed', opinion })
        }
      }
      if (verdicts.length === 0) {
        return { success: false, note: '用户未选择任何项：未记录裁决（挂起）' } as never
      }

      const nowTs = deps.now()
      const result = await deps.store.mutate('requirement-updated', (ledger) => {
        try {
          const applied = applyVerdicts(
            ledger, targetReq.id, sheet.version, verdicts,
            { kind: 'human', sessionId: windowKey }, nowTs, () => newCommentId(),
          )
          return { requirements: [applied.requirement], tasks: applied.reworkTasks }
        } catch (err) {
          reject('reqboard_accept_sheet 记录失败：' + ((err as Error).message ?? String(err)), (err as { code?: string }).code ?? 'REQBOARD_INVALID_INPUT')
        }
      })
      const changed = result.changed.requirements[0]
      if (changed === undefined) reject('reqboard_accept_sheet 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      const after = deps.store.snapshot().requirements.find(r => r.id === targetReq.id)
      const s = after?.verification?.sheet
      const pending = s?.items.filter(i => i.status === 'pending').length ?? 0
      const failed = s?.items.filter(i => i.status === 'failed').length ?? 0
      const reworkIds = result.changed.tasks.map(t => t.id)
      // 本批记录后若已全过 → 直接接着弹最终「验收通过并归档」确认（闭环）
      if (pending === 0 && failed === 0 && reworkIds.length === 0) {
        const fin2 = await finalizeIfAllPassed(s?.items.filter(i => i.status === 'passed').length ?? 0, 0)
        if (fin2 !== undefined) return fin2 as never
      }
      return {
        success: true,
        requirement_id: targetReq.id,
        sheet_version: sheet.version,
        recorded: verdicts.length,
        pending,
        passed: s?.items.filter(i => i.status === 'passed').length ?? 0,
        failed,
        ...(reworkIds.length > 0 ? { rework_tasks: reworkIds } : {}),
        note: reworkIds.length > 0
          ? '有不通过项：需求已打回 implementing，生成 ' + reworkIds.length + ' 个返工任务；修复后重新 verify_submit（v2 只含未过项）'
          : (pending > 0
              ? '本批已记录（剩 ' + pending + ' 项待验）：再次调 reqboard_accept_sheet 从断点继续'
              : '全部通过 → 请点「验收通过」归档（人工门）'),
      } as never
    },
  } as any)
}
