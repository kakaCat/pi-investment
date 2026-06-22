/**
 * Session utilities - 会话数据目录管理
 *
 * 从 akshare-ts/shared.ts 中提取出来的独立工具
 */

// ─── Session 数据目录（工具结果写入此目录，供 agent 按需 read）───
let _sessionDataDir: string | null = null;

/** 设置当前 session 的数据输出目录（每次会话初始化时调用） */
export function setSessionDataDir(dir: string): void {
  _sessionDataDir = dir;
}

/** 获取当前 session 的数据输出目录，fallback 到 /tmp */
export function getSessionDataDir(): string {
  return _sessionDataDir || "/tmp";
}
