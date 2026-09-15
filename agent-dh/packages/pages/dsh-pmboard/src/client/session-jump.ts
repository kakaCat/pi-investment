/**
 * 会话跳转 —— 把执行会话在 GUI 中打开（照抄 dsh-taskboard session-jump 模式）。
 * 惰性解析 sessions/workspaces 服务（apply 可能早于服务提供）；
 * 结果四分：opened / archived / missing / unavailable，UI 据此精确提示。
 *
 * @module dsh-pmboard/client/session-jump
 */

export type SessionJumpResult = 'opened' | 'archived' | 'missing' | 'unavailable'

export interface SessionsServiceFace {
  open(id: string): void
  refresh(): Promise<void>
  list: { getSnapshot(): { byId: Record<string, unknown> } }
}

export interface WorkspacesServiceFace {
  list: { getSnapshot(): { archivedSessionIds: readonly string[] } }
}

export interface SessionServiceAccess {
  getSessions(): SessionsServiceFace | undefined
  getWorkspaces(): WorkspacesServiceFace | undefined
}

/** 从 window 上的运行时服务投影惰性取（与 holdings solve-kit 同款宽容读取）。 */
export function windowServiceAccess(): SessionServiceAccess {
  const w = (): any => window as any
  return {
    getSessions: () => {
      try {
        const svc = w().__dshPmSessions ?? w().__dshPmCtx?.sessions
        if (svc && typeof svc.open === 'function' && svc.list) return svc as SessionsServiceFace
      } catch { /* 降级 unavailable */ }
      return undefined
    },
    getWorkspaces: () => {
      try {
        const svc = w().__dshPmWorkspaces ?? w().__dshPmCtx?.workspaces
        if (svc && svc.list) return svc as WorkspacesServiceFace
      } catch { /* 降级 */ }
      return undefined
    },
  }
}

/**
 * 已归档会话 id 集合（工作区服务不可用 / 字段缺失 → 空集）。
 *
 * 用途：归档会话「日志保留、侧栏不可见」——跳过去也打不开，所以 UI 把对应的
 * **窗口按钮置灰不可点**，而不是让人点了再弹「该会话已归档」。渲染层与下拉菜单
 * 共用本函数，保证判定口径一致。
 */
export function archivedSessionIds(access: SessionServiceAccess = windowServiceAccess()): ReadonlySet<string> {
  try {
    const ids = access.getWorkspaces()?.list.getSnapshot().archivedSessionIds ?? []
    return new Set<string>(ids)
  } catch { return new Set<string>() }
}

/**
 * 尝试打开会话。id 未命中时先 refresh() 重拉一次列表镜像再判
 * （镜像可能滞后：重连补拉/晚挂载）。
 */
export async function jumpToSession(access: SessionServiceAccess, sessionId: string): Promise<SessionJumpResult> {
  const sessions = access.getSessions()
  if (sessions === undefined) return 'unavailable'
  const inList = (sid: string): boolean => {
    try { return sessions.list.getSnapshot().byId[sid] !== undefined } catch { return false }
  }
  if (inList(sessionId)) {
    const archived = access.getWorkspaces()?.list.getSnapshot().archivedSessionIds ?? []
    if (archived.includes(sessionId)) return 'archived'
    sessions.open(sessionId)
    return 'opened'
  }
  try { await sessions.refresh() } catch { /* 刷新失败按 missing 处理 */ }
  if (inList(sessionId)) {
    const archived = access.getWorkspaces()?.list.getSnapshot().archivedSessionIds ?? []
    if (archived.includes(sessionId)) return 'archived'
    sessions.open(sessionId)
    return 'opened'
  }
  return 'missing'
}
