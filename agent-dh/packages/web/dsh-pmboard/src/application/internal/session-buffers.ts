/**
 * 会话痕迹纯缓冲（REQ-2e9473 t05 / t10）——工具调用痕迹与近期用户消息的**纯函数**。
 *
 * 2026-09-26 从 adapters/SessionProbeAdapter.ts 迁入：Dive 会话驱动器（application/dive/）
 * 要写这两张表，而它**不得反向 import adapters**（层边界门禁）→ 纯逻辑下沉到 application/internal。
 * SessionProbeAdapter 继续再导出这些符号，既有 import 路径（含测试）逐字不变。
 *
 * 零 I/O、零框架依赖：只接收 Map 参数并就地更新，函数体逐字搬移。
 *
 * @module dsh-pmboard/application/internal/session-buffers
 */

// 工具痕迹（REQ-2e9473 t05）：窗口维度记录 tool/call 事件，供 done 凭证门判定"开工以来有无真实工具动作"。
// ---------------------------------------------------------------------------

export interface ToolTraceEntry {
  at: number
  /** 会话事件层的工具名（注意：PTC 模式下内部调用一律呈现为 run_code——弱信号，t06 的强信号是文件证据） */
  name: string
}

/** 每窗口痕迹上限（环形截断，防内存膨胀）。 */
export const TOOL_TRACE_CAP = 500

/** 记录一条工具调用痕迹（环形截断）。 */
export function recordToolTrace(trace: Map<string, ToolTraceEntry[]>, windowKey: string, name: string, at: number): void {
  const list = trace.get(windowKey) ?? []
  list.push({ at, name })
  if (list.length > TOOL_TRACE_CAP) list.splice(0, list.length - TOOL_TRACE_CAP)
  trace.set(windowKey, list)
}

/** 统计窗口在某时点之后的工具活动（done 凭证门用：since = 任务 claimedAt）。 */
export function toolActivitySince(
  trace: Map<string, ToolTraceEntry[]>,
  windowKey: string,
  since: number,
): { total: number; byTool: Record<string, number>; workLike: number } {
  const list = (trace.get(windowKey) ?? []).filter(e => e.at >= since)
  const byTool: Record<string, number> = {}
  let workLike = 0
  for (const e of list) {
    byTool[e.name] = (byTool[e.name] ?? 0) + 1
    // 干活类工具：文件改动/命令执行/代码执行（reqboard_* 台账动作不算干活证据）
    if (['edit', 'write', 'bash', 'pwsh', 'run_code'].includes(e.name)) workLike += 1
  }
  return { total: list.length, byTool, workLike }
}

// ---------------------------------------------------------------------------
// 近期用户消息缓冲（REQ-2e9473 t10）：文字确认核验用。
// ---------------------------------------------------------------------------

/** 文字确认核验缓冲：窗口 → 最近真实用户消息（清洗后文本），evidence 必须命中其中一条。 */
export interface RecentUserMsg { text: string; at: number }

/** 缓冲上限与有效窗口。 */
export const RECENT_USER_MSG_CAP = 20
export const CONFIRM_EVIDENCE_WINDOW_MS = 60 * 60 * 1000

/** 记录一条真实用户消息（环形截断）。 */
export function recordRecentUserMsg(buf: Map<string, RecentUserMsg[]>, windowKey: string, text: string, at: number): void {
  const t = text.replace(/\s+/g, ' ').trim()
  if (t.length === 0) return
  const list = buf.get(windowKey) ?? []
  list.push({ text: t, at })
  if (list.length > RECENT_USER_MSG_CAP) list.splice(0, list.length - RECENT_USER_MSG_CAP)
  buf.set(windowKey, list)
}

/**
 * 核验 evidence 是否引用了一段时间内真实存在的用户消息原文（REQ-2e9473 t10 三通道③）。
 * 判定：缓冲内某条消息是 evidence 的子串，或 evidence 是该消息的子串（互为引用），
 * 且消息落在时间窗内。消息过短（<4 字符）不作证（"嗯""好"太易撞库）。
 */
export function evidenceMatchesRecentUserMsg(
  buf: Map<string, RecentUserMsg[]>,
  windowKey: string,
  evidence: string,
  now: number,
): { ok: boolean; matchedText?: string; reason?: string } {
  const ev = evidence.replace(/\s+/g, ' ').trim()
  const list = (buf.get(windowKey) ?? []).filter(m => now - m.at <= CONFIRM_EVIDENCE_WINDOW_MS)
  if (list.length === 0) return { ok: false, reason: '时间窗内没有该窗口的真实用户消息记录' }
  for (const m of list) {
    if (m.text.length >= 4 && (ev.includes(m.text) || m.text.includes(ev))) {
      return { ok: true, matchedText: m.text }
    }
  }
  return { ok: false, reason: 'evidence 未引用时间窗内任何真实用户消息原文（可能是编造或曲解）' }
}
