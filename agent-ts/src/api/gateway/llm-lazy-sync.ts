/**
 * 会话模型惰性同步：每个 gateway 会话记录上次所见的选择版本，
 * beforePrompt 时比对——版本变了就 setModel（"下一轮生效"）。
 */
export interface LazySyncDeps {
  getVersion: () => number;
  getSessionModel: () => unknown;
}

export function createLazyModelSync(deps: LazySyncDeps) {
  const seen = new Map<string, number>();
  return function sync(session: unknown, sessionKey: string): void {
    try {
      const version = deps.getVersion();
      const last = seen.get(sessionKey);
      if (last !== undefined && last !== version) {
        const s = session as { setModel?: (m: unknown) => void };
        if (typeof s.setModel === 'function') {
          s.setModel(deps.getSessionModel());
          console.log(`[llm] 会话 ${sessionKey} 惰性切换模型（v${last} → v${version}）`);
        }
      }
      seen.set(sessionKey, version);
    } catch (e) {
      console.warn('[llm] 惰性切换检查失败（不影响本次对话）:', (e as Error).message);
    }
  };
}
