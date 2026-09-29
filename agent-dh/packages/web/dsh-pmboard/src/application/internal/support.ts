/**
 * 用例共享支撑（REQ-47939a t6）——从 host/agent-tools.ts 逐字搬入的模块级助手。
 *
 * 这些助手原本散在工具壳里（认证 / done 凭证门的证据采集 / 闸门问题卡 / 直接立项写入），
 * 现在移入 application：工具壳与 HTTP 路由共用同一份，不再各自实现一遍。**规则本身仍在
 * domain/**（DoneEvidenceSpec / RequirementStatus …），本文件只做"取证据 + 调纯判定 + 抛错"。
 *
 * 零行为变更：拒绝条件、错误码、消息文案与搬迁前逐字一致。
 *
 * @module dsh-pmboard/application/internal/support
 */
import type { LedgerView, UseCaseDeps } from '../ports.js'
import { questionCardFor } from '../../domain/gate/GateCatalog.js'
import { checkDoneEvidence, findRecentAgentDoneTask } from '../../domain/workflow/DoneEvidenceSpec.js'
import { artifactNotifyText } from './artifact-gates.js'
// REQ-260927123256-196b FR-2/FR-4：挂起判定单点（未作答 且 台账未落章才拦）——守卫与回执共用。
import { livePendingConfirm, pendingConfirmRejectMessage } from './pending-guard.js'
import { isWindowBound, openRequirementsFor } from './window.js'
import {
  isSubtask,
  recordStatus,
  subtasksOf,
  type RequirementCategory,
  type RequirementRecord,
  type StageArtifact,
  type TaskRecord,
} from '../../shared/protocol.js'
import { captureSnapshot } from './token-usage.js'
import { checkParentSubtasksDone, checkSubtaskEvidence } from './subtask-evidence.js'
import { reportFileMtime } from './report-path.js'
// REQ-260924213231-b1c4 FR-7：降级路径（reqboard_create）复用弹框路径的文档位置缺省口径（单一事实源）。
import { CAPTURE_DEFAULTS } from './capture-mapping.js'
import { LIMITS } from '../../domain/limits.js'

/** 结构化认证失败：message 自带（CODE）文本；code 属性仅测试/直接执行消费。 */
export function reject(message: string, code: string): never {
  throw Object.assign(new Error(`${message}（${code}）`), { code })
}

/** 结构化读取调用 agent 的 id（identity 层：exec.agent 必须有 string id）。 */
export function agentIdFromExec(deps: UseCaseDeps, exec: unknown): string {
  return deps.session.windowKey(exec)
}

/** 尽力而为的 live-driver 认证（规则与文案在 SessionProbeAdapter，行为同搬迁前）。 */
export function requireLiveDriver(deps: UseCaseDeps, exec: unknown): void {
  deps.session.requireLiveDriver(exec)
}

/** 直接人工回合认证（规则与文案在 SessionProbeAdapter，行为同搬迁前）。 */
export function requireDirectHuman(deps: UseCaseDeps, exec: unknown): void {
  deps.session.requireDirectHuman(exec)
}

/**
 * 阶段通知简版（REQ-31e11f t4）：产物登记成功时通知请人审阅。
 * 用 ctx 里可用的通知通道（feishu_notify）；若无通知服务则 logger.info 降级，不阻断。
 */
export function notifyArtifactRegistered(
  _deps: UseCaseDeps,
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

/**
 * rollup 阻塞清单（REQ-2e9473 t02）：需求停在 implementing 但 R2 无法推进（存在未完成任务）
 * 时，返回阻塞任务清单；否则 undefined。用于 task_move / verify_submit 返回体显式告警——
 * REQ-6f39b5 事故 B 的教训：幽灵任务卡死 rollup 时静默无提示，agent 与用户都看不见。
 */
export function rollupBlockersOf(
  _ledger: LedgerView,
  tasks: readonly TaskRecord[],
  reqId: string,
  reqStatus: string,
): { id: string; title: string; status: string }[] | undefined {
  if (reqStatus !== 'implementing') return undefined
  // 队列任务（REQ-260927202051-f6df D4：`LedgerView.tasks` 随 v9 移除，任务由调用方从队列传入）
  const open = tasks.filter(t => t.requirementId === reqId && t.status !== 'canceled' && t.status !== 'done')
  if (open.length === 0) return undefined
  return open.map(t => ({ id: t.id, title: t.title, status: t.status }))
}

/**
 * done 凭证门（REQ-2e9473 t06/W2，事故 C/D 的硬门）：转 done 前的四重校验——
 *  ① 汇报前置：必须有 task_report 留痕（lastReport），且 completed/filesChanged 至少其一非空；
 *  ② 真实动作：**链出身以来**（需求/父卡/本卡 createdAt 最小值；老数据才退回开工 claimedAt）有
 *     干活类工具痕迹（edit/write/bash/run_code，弱信号），或汇报声明的文件真实存在且 mtime 晚于
 *     该基准（强信号）——25ms 速通两路都过不了；
 *  ③ 批量关闭节流：同需求 60s 内已有其他任务被本窗口关闭 → 拒（事故 C：一次调用关 4 个任务）；
 *  ④ 构建新鲜度：汇报改动涉及 packages/pages/<pkg>/src/ → 该包 lib/client.js 必须存在且
 *     新于最新 src 改动（事故 D：改了源码没构建，用户看到旧页面）。
 */
/** 页面插件构建新鲜度证据（父卡四重校验与子卡新口径共用）。 */
function pagesBuildEvidence(
  deps: UseCaseDeps,
  pagesSrc: readonly string[],
): { clientBuildExists: boolean; clientBuildMtime: number; newestPagesSrcMtime: number } {
  if (pagesSrc.length === 0) return { clientBuildExists: false, clientBuildMtime: 0, newestPagesSrcMtime: 0 }
  const pkg = /^packages\/pages\/([^/]+)\//.exec(pagesSrc[0] ?? '')?.[1] ?? ''
  const st = deps.docs.stat('packages/pages/' + pkg + '/lib/client.js')
  return {
    clientBuildExists: st !== undefined,
    clientBuildMtime: st?.mtimeMs ?? 0,
    newestPagesSrcMtime: Math.max(...pagesSrc.map((f) => deps.docs.stat(f)?.mtimeMs ?? 0)),
  }
}

/**
 * 链窗口基准（不可变出身，单调不后退）：需求 / 父卡 / 本卡 `createdAt` 的最小值。
 * 三者全缺（老数据）才退回本卡开工时刻——`claimedAt` 会被开工/重跑重写，不能当窗口起点
 * （REQ-260927144541-0481 D17 L1；2026-09-28 起父子两条证据路径共用本基准）。
 */
function chainBaselineOf(ledger: LedgerView, task: TaskRecord, parent?: TaskRecord): number {
  const requirement = ledger.requirements.find((r) => r.id === task.requirementId)
  const raw = Math.min(
    requirement?.createdAt ?? Infinity,
    parent?.createdAt ?? Infinity,
    task.createdAt ?? Infinity,
  )
  return Number.isFinite(raw) ? raw : (task.claimedAt ?? task.createdAt ?? 0)
}

/**
 * done 凭证门（REQ-2e9473 t06/W2，事故 C/D 的硬门）：转 done 前的四重校验。
 *
 * @param tasks 队列任务（REQ-260927202051-f6df D4：`LedgerView.tasks` 随 v9 移除）。
 *              `ledger` 只用于取需求记录（`ledger.requirements`）。
 */
export function assertDoneEvidence(
  deps: UseCaseDeps,
  windowKey: string,
  task: TaskRecord,
  ledger: LedgerView,
  tasks: readonly TaskRecord[],
): void {
  // 规则（四重校验与拒绝文案）在 domain/workflow/DoneEvidenceSpec.ts（REQ-47939a t3）；
  // 这里只负责取副作用证据（工具痕迹 / 文件 stat / 构建新鲜度）再交给纯判定。
  const rep = task.lastReport
  const filesChangedEarly = rep?.filesChanged ?? []
  // 基准 = 链出身（chainBaselineOf，单调不后退）——**父子同口径**（REQ-260927144541-0481 D17 L1）。
  // 此前父卡仍用 `claimedAt ?? createdAt`：claimedAt 由开工/重跑重写，轻档手工交付（先干活、
  // 后认领）会把已存在的交付判成「无改动」→ FINALIZE_PARENT 恒失败（2026-09-28 实测 t-dd5ba9
  // 开工 14:59:53 晚于交付 14:58:45，链在该父卡收尾处暂停）。子卡路径早已修过，父卡是同一缺陷的孪生。
  const chainSince = chainBaselineOf(ledger, task, isSubtask(task) ? tasks.find((t) => t.id === task.parentId) : undefined)
  const since = chainSince

  // REQ-4842fe t5：子卡走**新口径**（三项 + 构建新鲜度），豁免窗口活动与 60s 节流——
  // 干活的子代理在别的会话，"本窗口工具活动"对子卡恒不成立。
  if (isSubtask(task)) {
    // REQ-260927144541-0481（D17 结构性死路收口）：子卡是**父卡这条链**的一个阶段，交付可能在
    // 子卡 run 之前就已完成（轻档手工交付）——此时拿「子卡本次 run 起点」当新鲜度基准，必然把
    // 已存在的交付判成「无改动」。实测 t-c42bc0：run.ok=true、13 个上报文件全部存在，但 mtime
    // 14:55–15:04 早于 run 起点 15:25:48 → 子卡恒不过门、链必停。
    // 第一版修法取「父卡 claimedAt（缺省 createdAt）」——**基准仍会漂移**：claimedAt 由 ExecuteTask
    // 在每次重跑/重入时重写，链越跑基准越靠后，同一份交付会被前后两次判成不同结论。
    // 故基准改取**不可变出身**（requirement / 父卡 / 子卡 createdAt 的最小值，见下），窗口单调不后退；
    // 上报文件仍必须真实存在（写入族）——只把「谁的窗口」修对，不放弃文件系统证据。
    // L1 基准单调化（D17 病根）：基准已在函数入口统一取**不可变出身**（chainBaselineOf），
    // 父子同口径——claimedAt 会被重跑重写，不能当"链窗口起点"。
    const subPagesSrc = filesChangedEarly.filter((f) => /^packages\/pages\/[^/]+\/src\//.test(f))
    const build = pagesBuildEvidence(deps, subPagesSrc)
    const verdictSub = checkSubtaskEvidence({
      hasReport: rep !== undefined,
      reportFilesChanged: filesChangedEarly,
      reportCompleted: rep?.completed ?? [],
      run: task.lastRun,
      since: chainSince,
      // L2 证据形态分流：阶段决定该收文件证据还是结论证据（STAGE_EVIDENCE_KIND）。
      ...(task.stageKind !== undefined ? { stageKind: task.stageKind } : {}),
      // D15：路径归一——容忍子代理写相对 git 根的 `agent-dh/…` 前缀（工作区根已是 agent-dh）。
      fileMtimes: Object.fromEntries(filesChangedEarly.map((f) => [f, reportFileMtime(deps, f)])),
      pagesSrcFiles: subPagesSrc,
      ...build,
    })
    if (!verdictSub.ok) reject(verdictSub.reason, verdictSub.code)
    return
  }

  // REQ-4842fe t5：父卡收尾门（INV-5）——存在未 done 子卡时父卡不得 done。
  const subs = subtasksOf(tasks, task.id)
  if (subs.length > 0) {
    const verdictParent = checkParentSubtasksDone(subs)
    if (!verdictParent.ok) reject(verdictParent.reason, verdictParent.code)
  }

  const activity = deps.session.toolActivitySince(windowKey, since)
  const hasTraceWork = activity > 0
  const filesChanged = rep?.filesChanged ?? []
  const fileEvidence = filesChanged.some((f) => {
    const m = reportFileMtime(deps, f)
    return m !== undefined && m >= since
  })
  const nowTs = deps.clock.now()
  const recentDoneTask = findRecentAgentDoneTask(
    tasks, task.id, task.requirementId, nowTs, deps.doneThrottleMs ?? 60_000,
  )
  // ④ 页面插件构建新鲜度（事故 D）
  const pagesSrc = filesChanged.filter(f => /^packages\/pages\/[^/]+\/src\//.test(f))
  let clientBuildExists = false
  let clientBuildMtime = 0
  let newestPagesSrcMtime = 0
  if (pagesSrc.length > 0) {
    const pkg = /^packages\/pages\/([^/]+)\//.exec(pagesSrc[0])?.[1] ?? ''
    const st = deps.docs.stat('packages/pages/' + pkg + '/lib/client.js')
    if (st !== undefined) { clientBuildMtime = st.mtimeMs; clientBuildExists = true }
    newestPagesSrcMtime = Math.max(...pagesSrc.map((f) => deps.docs.stat(f)?.mtimeMs ?? 0))
  }
  const verdict = checkDoneEvidence({
    hasReport: rep !== undefined,
    reportFilesChanged: filesChanged,
    reportCompleted: rep?.completed ?? [],
    hasTraceWork,
    fileEvidence,
    ...(recentDoneTask !== undefined ? { recentDoneTask } : {}),
    pagesSrcFiles: pagesSrc,
    clientBuildExists,
    clientBuildMtime,
    newestPagesSrcMtime,
  })
  if (!verdict.ok) reject(verdict.reason, verdict.code)
}

/**
 * evidence 中的工作区路径候选（REQ-2e9473 t12）：只认已知根前缀 + 扩展名的 token，
 * 降低把散文误判成路径的概率（如"packages/x.ts 通过"仅取 packages/x.ts）。
 */
export function workspacePathCandidates(evidence: readonly string[]): string[] {
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
 *
 * REQ-e3b6a0 t2：文案与调用表达式已收敛进 `domain/gate/GateCatalog.questionCardFor`
 * （闸门唯一事实源），本处只做转发以保持既有调用点与输出逐字不变。
 */
export function gateQuestionCard(gateKind: string | undefined, from: string, to: string): string {
  return questionCardFor(gateKind, from, to)
}

/**
 * 文档位置取值与回落标记（REQ-260924213231-b1c4 T-10 / FR-7 / UC-4）——立项**降级路径**
 * （`reqboard_create`：弹框通道不可用、用户在对话里给三值时）与弹框路径共用同一份缺省口径
 * （`CAPTURE_DEFAULTS.docLocation`），堵住"降级丢第四问"。
 *
 * 规则：未传 / 空串 → 回落默认并标记 `usedDefault=true`（返回体 `defaults_used` 据此如实留痕，
 * 不静默猜）；形态非法（非字符串 / 绝对路径 / 含 `..` 上跳段）→ `REQBOARD_INVALID_INPUT`，
 * **不静默改路径**（design/use-cases.md UC-4 异常流）。
 */
export function resolveDocBasePath(raw: unknown): { docBasePath: string; usedDefault: boolean } {
  if (raw === undefined || raw === null) {
    return { docBasePath: CAPTURE_DEFAULTS.docLocation, usedDefault: true }
  }
  if (typeof raw !== 'string') {
    reject('reqboard_create 未执行：doc_location 必须是工作区相对目录（字符串）', 'REQBOARD_INVALID_INPUT')
  }
  const p = raw.trim()
  if (p.length === 0) return { docBasePath: CAPTURE_DEFAULTS.docLocation, usedDefault: true }
  if (p.length > LIMITS.pathMax) {
    reject(`reqboard_create 未执行：doc_location 超长（≤${LIMITS.pathMax} 字符）`, 'REQBOARD_INVALID_INPUT')
  }
  if (!isWorkspaceRelativeDir(p)) {
    reject(
      `reqboard_create 未执行：doc_location 必须是工作区相对目录（收到 ${p}）——绝对路径与含 .. 的路径一律不接受，不静默改路径`,
      'REQBOARD_INVALID_INPUT',
    )
  }
  return { docBasePath: p, usedDefault: false }
}

/** 工作区相对目录判定：拒绝绝对路径（POSIX / Windows 盘符 / UNC / ~）与 `..` 上跳段。 */
function isWorkspaceRelativeDir(p: string): boolean {
  if (p.startsWith('/') || p.startsWith('~') || p.startsWith('\\')) return false
  if (/^[A-Za-z]:[\\/]/.test(p)) return false
  return !p.split(/[\\/]+/).includes('..')
}

/**
 * 直接立项写入：store.mutate('requirement-created') push RequirementRecord
 * （status='draft'，sourceSessionId=windowKey，actor={kind:'human'}——弹框作答
 * = 用户确认，语义等同看板 confirm）。幂等：mutator 内窗口已 bound → return
 * undefined 中止；中止后若快照显示已绑定 → REQBOARD_WINDOW_BOUND 拒绝。
 */
export async function createRequirementDirect(
  deps: UseCaseDeps,
  windowKey: string,
  input: { title: string; category: RequirementCategory; description: string; reason: string; promptDifficulty?: string; docBasePath?: string },
): Promise<RequirementRecord> {
  const nowTs = deps.clock.now()
  // REQ-260924213231-b1c4 FR-7：docBasePath 缺省时写既有默认值——回落要**落在台账**（不只留在返回体），
  // 否则"降级路径丢第四问"只是换了地方丢。与 requirementDocPath() 的缺省分支同值。
  const docBasePath = (input.docBasePath ?? '').trim() || CAPTURE_DEFAULTS.docLocation
  const result = await deps.repo.mutate('requirement-created', (ledger) => {
    if (isWindowBound(ledger, windowKey)) return undefined // 幂等：已绑定 → 不重复立项
    const actor = { kind: 'human' } as const
    const req: RequirementRecord = {
      id: deps.ids.requirement(),
      title: input.title,
      description: input.description,
      category: input.category,
      promptDifficulty: input.promptDifficulty as any, // 提示词难度级别
      docBasePath,
      sourceSessionId: windowKey,
      status: 'draft',
      blocked: false,
      comments: [
        {
          id: deps.ids.comment(),
          body: [
            `[会话捕获] 用户经四问弹框确认立项（会话 ${windowKey}）`,
            `名称/分类/难度为用户确认值：${input.title}（${input.category}，提示词难度：${input.promptDifficulty ?? 'standard'}）`,
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
    // REQ-a33899：立项即记 draft 状态事件 + 写时快照——否则「立项」节点没有进入快照，
    // 该节点消耗永远算不出来（首段也应当可归因）。
    recordStatus(req, 'draft', nowTs, actor, undefined, captureSnapshot(deps, windowKey))
    ledger.requirements.push(req)
    return { requirements: [req] }
  })
  const createdReqs = result.changed.requirements ?? []
  if (createdReqs.length > 0) return createdReqs[0]
  if (openRequirementsFor(deps.repo.snapshot(), windowKey).length > 0) {
    reject('reqboard_create 未写入：本窗口已绑定进行中需求，勿重复立项', 'REQBOARD_WINDOW_BOUND')
  }
  reject('reqboard_create 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
}

/** 需求简要投影（open_requirements 输出用；不泄漏 comments 等内部字段）。 */
export function projectRequirement(r: RequirementRecord): { id: string; title: string; status: string; category: string } {
  return {
    id: r.id,
    title: r.title,
    status: r.status,
    category: r.category ?? '',
  }
}


/**
 * 用例边界错误码映射（REQ-260927100007-b8ba FR-7）：domain 状态机抛的是领域码
 * （human_gate / system_gate），而 agent 侧工具的传输契约是 REQBOARD_HUMAN_GATE —— 在用例
 * 边界统一映射一次；工具壳与看板 HTTP 路由各自保持既有码不变（看板仍读 human_gate）。
 */
export function mapAgentError(err: unknown): never {
  if ((err as { code?: unknown } | null | undefined)?.code === 'human_gate') {
    const message = (err as Error).message ?? '该转移是人工闸门，仅人可操作'
    throw Object.assign(new Error(message + '（REQBOARD_HUMAN_GATE）'), { code: 'REQBOARD_HUMAN_GATE' })
  }
  throw err
}

/**
 * 确认门挂起期间的**同窗口停手守卫**（REQ-260927100007-b8ba FR-9；REQ-260927123256-196b FR-2/FR-4）。
 *
 * 缺省阻塞路径在**进入等待前**就登记 ticket（见 use-cases/AskConfirm.ts），守卫因此在整个等待期
 * 生效：写路径工具入口一律先过这里，命中挂起 → 代码级拒绝 REQBOARD_CONFIRM_PENDING，并给出
 * 三条恢复路径（取回执 / 看板确认 / 重新发起覆盖）。
 *
 * 判定单点在 `internal/pending-guard.ts` 的 `livePendingConfirm`：台账已落章（人走看板/证据通道
 * 作答）时放行——否则「人已确认但挂起记录未 settle」的陈旧记录会把窗口锁死。
 * （reqboard_status / reqboard_confirm_receipt 刻意不过此守卫——否则人无法解除挂起。）
 *
 * serves: FR-2 / FR-4（REQ-260927123256-196b t3）；判定口径见 pending-guard.livePendingConfirm。
 */
export function assertNoPendingConfirm(deps: UseCaseDeps, windowKey: string): void {
  const p = livePendingConfirm(deps, windowKey)
  if (p === undefined) return
  reject(pendingConfirmRejectMessage(p), 'REQBOARD_CONFIRM_PENDING')
}
