/**
 * Session Services 自修复模块
 *
 * 背景：SDK 0.73+ 后，AgentSessionServices 不再由 createAgentSession 返回，
 * 必须通过 createAgentSessionServices 独立创建。历史上此处因返回值缺字段
 * 导致启动直接 crash（"Session services not initialized"）。
 *
 * 本模块的契约：**永不抛异常**——任何一环失败都逐层降级：
 * - createServicesSafely: 主 agentDir → 默认 agentDir → 最小 stub
 * - openSessionManagerSafely: 文件缺失/损坏 → undefined（调用方走全新会话）
 */
import { existsSync } from "fs";
import {
  createAgentSessionServices,
  getAgentDir,
  SessionManager,
  type AgentSessionServices,
} from "../../sdk-facade.js";

function errMsg(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * 创建 cwd 绑定的 runtime services，带分层降级，永不抛异常。
 *
 * 降级链：
 *   1. createAgentSessionServices({ cwd, agentDir })（agentDir 默认 getAgentDir()）
 *   2. createAgentSessionServices({ cwd, agentDir: getAgentDir() })（主 agentDir 有问题时）
 *   3. 最小 stub（仅 cwd/agentDir/diagnostics），保证 runtime 拿到合法 cwd
 */
export async function createServicesSafely(
  cwd: string,
  agentDir?: string
): Promise<AgentSessionServices> {
  const primaryAgentDir = agentDir ?? getAgentDir();

  try {
    return (await createAgentSessionServices({
      cwd,
      agentDir: primaryAgentDir,
    })) as unknown as AgentSessionServices;
  } catch (error) {
    console.warn(
      `⚠️  services 创建失败（agentDir=${primaryAgentDir}），尝试默认 agentDir: ${errMsg(error)}`
    );
  }

  try {
    return (await createAgentSessionServices({
      cwd,
      agentDir: getAgentDir(),
    })) as unknown as AgentSessionServices;
  } catch (error) {
    console.warn(`⚠️  services 创建再次失败，降级为最小 stub: ${errMsg(error)}`);
  }

  return {
    cwd,
    agentDir: primaryAgentDir,
    diagnostics: [
      { type: "error", message: "AgentSessionServices degraded to minimal stub" },
    ],
  } as unknown as AgentSessionServices;
}

/**
 * 安全打开已有 SDK session 文件。
 * 文件缺失或损坏时返回 undefined（调用方应走全新会话），永不抛异常。
 */
export function openSessionManagerSafely(sessionFile: unknown): unknown | undefined {
  if (!sessionFile || typeof sessionFile !== "string") return undefined;

  try {
    if (!existsSync(sessionFile)) {
      console.warn(`⚠️  恢复的 session 文件不存在，改用全新会话: ${sessionFile}`);
      return undefined;
    }
    return SessionManager.open(sessionFile);
  } catch (error) {
    console.warn(
      `⚠️  session 文件损坏（${errMsg(error)}），改用全新会话: ${sessionFile}`
    );
    return undefined;
  }
}
