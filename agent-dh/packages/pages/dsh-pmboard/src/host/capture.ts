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
  'draft', 'reviewing', 'decomposing', 'implementing', 'accepting',
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