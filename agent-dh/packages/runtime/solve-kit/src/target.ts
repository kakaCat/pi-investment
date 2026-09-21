// @pi-investment/solve-kit · host 共用目标解析与投递原语（「我来解决」的公共底座）。
// 2026-09-14 从 host.ts 抽出：执行看板（task/error 快照）与公告板（board 帖子）两档共用同一套
// 窗口解析 → followup 投递语义，避免各页面各写一份（公告板 GUI 动作曾自写一套并因此失修）。

export interface ActionTarget {
  /** 目标 agent（root 会话），含 followup 投递能力 */
  agent: unknown
  sessionId: string
  /** 展示用窗口标签（session-<uuid> → w-<前8>，余者原样） */
  window: string
}

export interface SolveKitHostDeps {
  /** 解析目标会话 → 在线 agent；无 to_session 时回退 from_session（默认当前窗口），
   *  再回退主 root；查无 → null。to_session 传 true=精确命中（投递指定窗口禁止回退） */
  resolveAgent: (sessionId?: string, exactOnly?: boolean) => ActionTarget | null
}

/** session id → 展示窗口标签（与 lifecycle windowCode 同口径） */
export function windowCode(id: string): string {
  return id.startsWith('session-') ? 'w-' + id.slice(8, 16) : id
}

/** 把消息 followup 投递到目标窗口（唯一投递实现，两档共用） */
export async function deliverMessage(
  target: ActionTarget | null,
  message: unknown,
): Promise<{ delivered: boolean; error?: string; target?: { sessionId: string; window: string } }> {
  if (!target) return { delivered: false, error: '目标窗口不在线（未解析到 agent）' }
  const agent = target.agent as any
  if (typeof agent?.followup !== 'function') {
    return { delivered: false, error: '目标 agent 无 followup 投递能力', target: { sessionId: target.sessionId, window: target.window } }
  }
  try {
    await agent.followup(message)
    return { delivered: true, target: { sessionId: target.sessionId, window: target.window } }
  } catch (e) {
    return { delivered: false, error: '投递失败：' + (e instanceof Error ? e.message : String(e)), target: { sessionId: target.sessionId, window: target.window } }
  }
}
