/**
 * reqboard 窗口捕获（hook）判定模块 —— 用户裁定 · 创建即立项（两问弹框 = 立项门）。
 *
 * 职责（B：按窗口条件注入）：systemPrompt 组装时为每个 agent 窗口求值本窗口
 * 的捕获引导文本。判定依据完全来自台账（requirement records + triages）：
 *   - bound      = 该窗口（windowKey = agent.id / sessionId）已绑定进行中的需求
 *                  （requirements.sourceSessionId === windowKey，或该窗口的 triage
 *                  确认产出过 resultRequirementId 指向仍 open 的 req）
 *   - hasPending = 该窗口有一条**遗留** pending 建议卡（旧流程 triage 产物；新流程
 *                  不再产生 pending —— 弹框作答即立项，无建议卡中间态）
 * 仅 unbound 且无 pending 的窗口返回引导文本；否则返回 ''（renderPrompt 会
 * 滤掉空段 → 零噪音，实证 dsh-system-prompt L65-68）。
 *
 * 捕获语义（用户裁定）：unbound 窗口出现值得立项的新工作 → 引导 LLM 先弹「两问
 * 确认」（ask_user_question：需求名称 + 需求类型）→ **用户作答 = 立项确认** →
 * 按确认值调 reqboard_create 直接创建 REQ（创建即立项，无待归类/建议卡中间态，
 * 看板立即可见）。
 *
 * 引导文本为纯字面量（不插 {{变量}}——renderPrompt 插值先于空段过滤，
 * 未知变量会 throw）。text 同步求值：store.snapshot() 同步可用。
 *
 * @module dsh-pmboard/host/capture
 */

import type { ReqboardLedger, RequirementRecord, TriageRecord } from '../shared/protocol.js'

/** 仍处进行中的需求状态（bound 判定用）；done/archived/canceled 视为已结束。 */
const OPEN_REQ_STATUSES: ReadonlySet<string> = new Set([
  'draft', 'brainstorming', 'planning', 'decomposing', 'implementing', 'accepting',
])

/** 从组装 context 提取窗口键：agent.id（'session-<uuid>'）优先，scope 兜底。 */
export function windowKeyFromContext(context: { agent?: { id?: unknown }; scope?: unknown } | undefined): string | undefined {
  const agentId = context?.agent?.id
  if (typeof agentId === 'string' && agentId.length > 0) return agentId
  const scope = context?.scope
  if (typeof scope === 'string' && scope.length > 0) return scope
  return undefined
}

function isOpenReq(req: RequirementRecord): boolean {
  return OPEN_REQ_STATUSES.has(req.status)
}

/**
 * 该窗口是否已绑定进行中的需求。规则（B：从需求记录判断）：
 *  1. 台账存在 open req 且 sourceSessionId === windowKey（窗口直接立项/自动立项）；
 *  2. 该窗口某条 triage 已确认（bind_req/create_req）且其 resultRequirementId(s)
 *     指向仍 open 的 req（bind 场景 req.sourceSessionId 可能不是本窗口，需窗口侧锚点）。
 */
export function isWindowBound(ledger: ReqboardLedger, windowKey: string): boolean {
  if (ledger.requirements.some(r => r.sourceSessionId === windowKey && isOpenReq(r))) return true
  for (const tri of ledger.triages) {
    if (tri.sessionId !== windowKey) continue
    const anchorIds: string[] = []
    if (tri.resultRequirementId) anchorIds.push(tri.resultRequirementId)
    if (Array.isArray(tri.resultRequirementIds)) anchorIds.push(...tri.resultRequirementIds)
    for (const reqId of anchorIds) {
      const req = ledger.requirements.find(r => r.id === reqId)
      if (req && isOpenReq(req)) return true
    }
  }
  return false
}

/** 该窗口绑定的 open 需求里，仍处 draft 的（接手推进信号 R1 用）。 */
export function draftRequirementsFor(ledger: ReqboardLedger, windowKey: string): RequirementRecord[] {
  return openRequirementsFor(ledger, windowKey).filter(r => r.status === 'draft')
}

/** 该窗口是否已有**遗留** pending 建议卡（旧流程 triage 产物；仅旧窗口会残留，已建议 → 抑制重复引导）。 */
export function hasPendingSuggestion(ledger: ReqboardLedger, windowKey: string): boolean {
  return ledger.triages.some(t => t.sessionId === windowKey && t.status === 'pending')
}

/** 该窗口最近的**遗留** pending 建议卡（旧流程 triage 产物；供 reqboard_status 展示，新流程不再产生）。 */
export function pendingSuggestionFor(ledger: ReqboardLedger, windowKey: string): TriageRecord | undefined {
  return ledger.triages
    .filter(t => t.sessionId === windowKey && t.status === 'pending')
    .sort((a, b) => b.createdAt - a.createdAt)[0]
}

/** 该窗口进行中的需求（简要投影，供引导文本与 reqboard_status 使用）。 */
export function openRequirementsFor(ledger: ReqboardLedger, windowKey: string): RequirementRecord[] {
  const direct = ledger.requirements.filter(r => r.sourceSessionId === windowKey && isOpenReq(r))
  const anchored = new Map<string, RequirementRecord>()
  for (const tri of ledger.triages) {
    if (tri.sessionId !== windowKey) continue
    const ids: string[] = []
    if (tri.resultRequirementId) ids.push(tri.resultRequirementId)
    if (Array.isArray(tri.resultRequirementIds)) ids.push(...tri.resultRequirementIds)
    for (const reqId of ids) {
      const req = ledger.requirements.find(r => r.id === reqId)
      if (req && isOpenReq(req) && !anchored.has(req.id)) anchored.set(req.id, req)
    }
  }
  const seen = new Set<string>()
  const out: RequirementRecord[] = []
  for (const r of [...direct, ...anchored.values()]) {
    if (seen.has(r.id)) continue
    seen.add(r.id)
    out.push(r)
  }
  return out
}

/**
 * 待捕获消息登记（确定性消息 hook 写入、capture section 消费的瞬态信号）。
 * 不进台账——它是「用户消息刚到达、窗口需要走立项评估」的一次性触发信号，
 * turn/end 后由 hook 清除（消费完毕）。
 */
export interface PendingCaptureMessage {
  windowKey: string
  /** 清洗后的用户消息文本（供注入引用；纯系统块/噪声消息不会登记）。 */
  text: string
  capturedAt: number
}

/**
 * 该窗口的捕获引导 section 文本（乙：提示 agent 识别新工作 → 两问弹框确认 →
 * reqboard_create 直接立项）。bound / 已有遗留 pending / 无法取 windowKey →
 * 返回 ''（零噪音）。永不返回 undefined。
 *
 * 第三参 pending 为确定性消息 hook 登记的本窗口「待捕获候选」：命中时返回
 * 引用该用户消息原文的针对性立项提示（用户裁定：消息到达 → hook 检查窗口是否
 * 需要立项捕获 → 注入提示词让 LLM 弹两问确认 → 直接建 REQ），未命中维持静态引导。
 * 向后兼容：不传 pending 时行为与旧版完全一致（capture.test.ts 三分支不变）。
 */
export function captureSectionText(
  ledger: ReqboardLedger,
  context: unknown,
  pending?: PendingCaptureMessage | undefined,
): string {
  const windowKey = windowKeyFromContext(context as { agent?: { id?: unknown }; scope?: unknown })
  if (!windowKey) return ''
  if (isWindowBound(ledger, windowKey)) return ''
  if (hasPendingSuggestion(ledger, windowKey)) return ''
  if (pending && pending.windowKey === windowKey && pending.text.trim().length > 0) {
    return capturePromptForMessage(windowKey, pending.text)
  }
  return captureGuidanceText(windowKey)
}

/**
 * 绑定窗口的「推进纪律」段 —— 本窗口已绑定进行中需求时注入；未绑定 → ''。
 *
 * 为什么需要：此前 bound 窗口的 section 返回 ''（零噪音），窗口 agent 根本不知道
 * 自己名下有需求、更不知道可以推进状态 → 需求建卡后只能等人点按钮（用户反馈
 * 「agent 自己不能推进吗，还需要用户手动推进」）。本段把「状态由窗口自己维护」
 * 变成提示词里的明确纪律，窗口在里程碑处主动调 reqboard_move。
 */
export function boundSectionText(ledger: ReqboardLedger, context: unknown): string {
  const windowKey = windowKeyFromContext(context as { agent?: { id?: unknown }; scope?: unknown })
  if (windowKey === undefined) return ''
  const open = openRequirementsFor(ledger, windowKey)
  if (open.length === 0) return ''
  return [
    `## 项目看板（reqboard · 本窗口 ${windowKey.slice(0, 16)} 已绑定需求）`,
    '',
    '本窗口名下有进行中的需求：',
    ...open.map(r => `- ${r.id}《${r.title}》当前状态：${r.status}`),
    '',
    '流水线（状态就是阶段，从立项一路走到交付）：',
    '- draft 立项 → brainstorming 头脑风暴（探边界/方案）→ planning 写计划 →',
    '  decomposing 拆分（落库任务 DAG）→ implementing 执行 → accepting 验收 → done 完成；',
    '- 方案谈定 → reqboard_move 到 planning（写计划属于这个阶段）；',
    '',
    '计划模式（拆分的前置闸门 · 唯一需要人点头的地方）：',
    '- 评审阶段先把方案写成实施计划 → reqboard_plan_submit（path = 工作区计划文档，',
    '  summary = 一段人能读懂的目标+做法，tasks = 将来要落库的任务表：',
    '  key/title/phase/side/depends_on/acceptance，粒度与依赖在这里定死）；',
    '- 提交后请人在项目看板点「批准计划」——未批准时 reqboard_decompose 被代码级拒绝；',
    '- 获批后 reqboard_decompose 落库任务卡（不传 tasks = 直接落库批准的计划；',
    '  传了 tasks 则必须与计划 key 一致，防止「批了 A 落库 B」）；',
    '- 方案要改 → 重新 reqboard_plan_submit（旧批准自动作废，需重新批准）。',
    '',
    '状态推进纪律（计划批准之后，其余都由窗口自己维护，不需要用户手动点按钮）：',
    '- 方案敲定 → reqboard_decompose 把需求拆成任务 DAG 落库（真拆分：写台账任务卡，',
    '  看板「任务」页与甘特图据此渲染；depends_on 用批次内 key 引用同批任务）；',
    '- 拆分后需求会自动进入拆分态；任务开工/完成用 reqboard_task_move 推进',
    '  （todo → in_progress → testing → in_review → done；开工时会自动记一段执行时间）；',
    '- 任务全部 done 时系统自动把需求推进到 accepting（验收）；交付并自检通过后',
    '  用 reqboard_move 自行推进到 done。',
    '- 只有「取消需求/归档/取消任务」必须人操作（agent 调用会被代码级拒绝）。',
    '- 推进时用 reason 写清做了什么（进需求留痕，供复盘与验收）。',
    '',
    '验收（人工审核，别自己判过）：',
    '- 交付完成 → reqboard_verify_submit（summary = 交付结论；evidence = 可复核的证据：',
    '  命令+输出摘要 / 报告路径 / 截图路径），需求进入验收态等人审核；',
    '- 「验收通过」只有人能点；被退回 → 按人的意见返工后再提交。',
    '',
    '归档（先备材料，人再点）：',
    '- 需求完成后 → reqboard_archive_submit（需求目录 docs/requirements/REQ-xxxxxx、',
    '  目录内文档清单、合并去向 merged_into、一句话索引条目）；',
    '- 合并去向与必填文档按需求类型限定（feature→architecture/guides，bug→known-issues，',
    '  spike→research，refactor→architecture/work-logs，chore→work-logs），规范见',
    '  agent-dh/docs/architecture/requirement-archive.md；缺项会被代码级拒绝；',
    '- 归档材料里写了的合并去向，必须真的把那部分结论写进对应的项目文档；',
    '- 金字塔生长：feature/refactor/spike 必须在材料里申报 manual_updates（更新了哪份文档的哪一节、',
    '  多了什么认知），说明书是 docs/architecture/project-manual.md；bug/doc/chore 写 manual_note 说明即可；',
    '- docs 按 wiki 维护：新页面要有 front-matter 并挂进首页/上层页，未写的主题进首页「待写页」；',
    '  收工前可跑 python3 agent-dh/scripts/wiki_probe.py 自检死链/孤儿页。',
  ].join('\n')
}

/**
 * 针对性立项提示（消息事件 hook 命中时注入）：引用刚到达的用户消息原文，
 * 指示 LLM 判断该输入是否值得立项——值得则【两问弹框 = 立项门 → 直接建 REQ】：
 * 先 ask_user_question 向用户弹两问——「需求名称」（选项由本条消息上下文推导、
 * 最贴切一项置首标注 (Recommended)、允许自定义）与「需求类型」（feature/bug/doc/
 * refactor/spike/chore，同 (Recommended) 置首可改选）；**用户作答即立项确认**，
 * 随后按确认值调 reqboard_create 直接创建 REQ（创建即立项，无待归类/建议卡
 * 中间态，看板立即可见）。只是闲聊 / 追问进度则正常回复，不弹框不立项。
 * 判定留给 LLM（窗口 agent 自身回合），hook 只保证确定性触发。全部字面量。
 */
export function capturePromptForMessage(windowKey: string, text: string): string {
  const trimmed = text.trim().replace(/\s+/g, ' ')
  const snippet = trimmed.slice(0, 300)
  return [
    `## 项目捕获（reqboard · 本窗口 ${windowKey.slice(0, 16)} 检测到用户新输入）`,
    '',
    '用户刚刚发来一条消息，其中可能包含值得立项的新工作意图（新功能 / 缺陷修复 /',
    '文档 / 重构 / 技术调研 / 维护事项）。请先判断该输入是否属于这类工作：',
    '',
    '- 值得立项 → 先弹「两问确认」（弹框即立项门，作答即立项）：',
    '  1) 调用 ask_user_question 一次发两个问题向用户确认——',
    '     问题一「需求名称」：按本条消息上下文给出候选标题选项，最贴切的一项放首位',
    '       并标注 (Recommended)，允许用户选择或自定义输入最终名称；',
    '     问题二「需求类型」：选项 feature / bug / doc / refactor / spike / chore，',
    '       最符合的一项放首位并标注 (Recommended)，允许用户改选或自定义；',
    '  2) 用户作答后（= 立项确认），立即按用户确认值调 reqboard_create 直接创建需求：',
    '     title = 用户确认的需求名称，category = 用户选择的需求类型，',
    '     summary = 本次工作摘要，reason = 立项依据（引用本条消息原文）；',
    '',
    '- 只是闲聊、询问进度、继续之前话题或无需立项 → 正常回复即可，不要弹框、不要立项。',
    '',
    '本次待判断的用户消息（节选，最多 300 字）：',
    '',
    `> ${snippet}${trimmed.length > 300 ? '…' : ''}`,
    '',
    '注意：reqboard_create 创建即立项（REQ 立即在看板 draft 泳道可见，无待归类/建议卡',
    '中间态）；本窗口创建后即绑定该需求。未弹框或用户未作答时不要调用、不要宣称"已立项"。',
  ].join('\n')
}

/** 引导文本（纯字面量）。窗口已完成/取消/归档全部需求后重新变为 unbound → 引导复现。 */
export function captureGuidanceText(windowKey: string): string {
  // 全部字面量，无 {{变量}}。短小精炼，避免挤占上下文预算。
  return [
    `## 项目捕获（reqboard · 本窗口 ${windowKey.slice(0, 16)} 未绑定需求）`,
    '',
    '本窗口当前没有进行中的需求记录。若用户在本窗口提出了新的工作意图',
    '（新功能 / 缺陷修复 / 文档 / 重构 / 技术调研 / 维护事项），且该工作值得立项，',
    '先调用 ask_user_question 弹「两问确认」：问题一「需求名称」（按上下文给出候选',
    '选项，最贴切一项置首标注 (Recommended)，允许用户自定义）；问题二「需求类型」',
    '（feature / bug / doc / refactor / spike / chore，同 (Recommended) 置首可改选）。',
    '用户作答即立项确认——按确认值调 reqboard_create 直接创建 REQ（创建即立项，',
    '无待归类/建议卡中间态）：title = 确认名称、category = 确认类型、',
    'summary = 工作摘要、reason = 立项依据。',
    '',
    '仅闲聊或询问已有需求进度时无需弹框、无需立项。',
  ].join('\n')
}