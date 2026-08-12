/**
 * Agent Loop - 基于 pi-coding-agent SDK 的核心循环
 *
 * 职责:
 * - AgentSession 的创建与复用
 * - 工具初始化（内置 + 插件 + 投资工具）
 * - Skills 加载
 * - 每轮消息的收发与上下文管理
 */
import {
  AgentSession,
  createAgentSession,
  loadSkills,
  type Skill,
  type AgentSessionServices,
  type CreateSessionResult,
} from "../../sdk-facade.js";
import { createServicesSafely, openSessionManagerSafely } from "./session-services.js";
import { allCustomTools, initCompactTool, initBrowserTool, initTaskTools, initBackgroundManager, initRestartAgentTool } from "../../infrastructure/tools/index.js";
import { initSkillGuard } from "../../infrastructure/tools/skill-guard.js";
import type { ToolDefinition } from "../../infrastructure/tools/index.js";
import { setPlanToolContext } from "../../infrastructure/tools/agent/plan-tool.js";
import { loadPlugins } from "../../infrastructure/plugins/index.js";
import { initMemoryProvider, getMemoryProvider } from "../../services/memory/index.js";
import { join } from "path";
import { paths } from "../../config/config.js";
import { getLLM } from "../../services/llm/index.js";
import { createAppResourceLoader } from "../../api/extensions/model-command.js";
import { getSessionDir, getSessionKey, logSystemPrompt, logBootstrapFiles } from "../../infrastructure/logging/observable-logger.js";
import { initSkillsBlock, buildAgentSystemPrompt } from "./system-prompt.js";
import { getBootstrapData } from "../../config/config.js";
import { initSkillRouter } from "../../services/intelligence/skill-router.js";
import { setSessionDataDir } from "../../infrastructure/tools/shared/session-utils.js";
import { normalizeAssistantUsages } from "./session-adapter.js";
import { ErrorHandlers, ErrorSeverity, handleAgentError } from "./error-handler.js";

/**
 * Session 上下文类型
 *
 * 注意：'cron_evolution' 已废弃，代码生成现在由 Codex 负责
 */
export interface SessionContext {
  type: 'interactive' | 'cron_evolution' | 'cron_review' | 'background_task';
  sessionId: string;
  metadata?: Record<string, any>;
}

// 全局会话实例，复用同一个 session
let session: AgentSession | null = null;
// 插件贡献的工具（在 getSession 中初始化）
let pluginTools: ToolDefinition[] = [];
// 当前 session 的上下文
let sessionContext: SessionContext | null = null;
// 当前 session 的 services（用于 AgentSessionRuntime 构造）
let sessionServices: AgentSessionServices | null = null;
// 一次性基础设施初始化标记（skills/插件/工具只加载一次，/resume 不重复）
let baseInitialized = false;
let cachedSkills: Skill[] = [];
let cachedTools: ToolDefinition[] = [];

/** 返回内置工具 + 插件工具的合并列表 */
function getEffectiveTools(): ToolDefinition[] {
  return [...allCustomTools, ...pluginTools as any[]] as ToolDefinition[];
}

/**
 * 加载项目中的 skills，打印加载结果
 */
function loadProjectSkills(): Skill[] {
  try {
    // @ts-ignore - Type mismatch from SDK update
    const result = loadSkills({ cwd: paths.root, skillPaths: [join(paths.root, "skills")] } as any);

    if ((result as any).warnings?.length > 0) {
      console.warn("⚠️  Skills 加载警告:");
      (result as any).warnings.forEach((w: any) => {
        console.warn(`  - ${w.skillPath}: ${w.message}`);
      });
    }

    if (result.skills.length > 0) {
      console.log(`✅ 已加载 ${result.skills.length} 个 skills:`);
      result.skills.forEach(s => console.log(`  - ${s.name}: ${s.description}`));
    }

    return result.skills;
  } catch (error) {
    return ErrorHandlers.warn(error, "Skills 加载失败", []);
  }
}

/**
 * 根据上下文类型构建 system prompt
 *
 * 注意（2026-08-12 修补）：系统提示词保持同步构建、每 session 只构建一次（prompt cache 窄腰原则）。
 * 记忆召回注入不在此处——在 session-factory 的 prompt 包装层按消息注入。
 */
function buildSystemPromptForContext(ctx: SessionContext | null): string {
  // 所有上下文类型都使用投资决策 prompt
  // 代码生成已委托给 Codex，不再使用投资 Agent
  return buildAgentSystemPrompt({
    memoryContext: "",
    dailyMemory: "",
    tools: getEffectiveTools(),
    workspaceDir: paths.root,
  });
}

/**
 * 根据上下文类型获取工具列表
 */
function getToolsForContext(ctx: SessionContext | null): ToolDefinition[] {
  // 所有上下文类型都使用完整工具集
  return getEffectiveTools();
}

/**
 * 一次性基础设施初始化（skills / 插件 / 工具注册表）
 * 进程内只执行一次；/resume 切换 session 时直接复用缓存，不重复加载。
 */
async function initBaseOnce(): Promise<void> {
  if (baseInitialized) return;

  // W1.4: 初始化 Memory Provider（替代旧的 initMemoryTools）
  const sessionKind = sessionContext?.type === 'cron_review' ? 'cron' :
                      sessionContext?.type === 'background_task' ? 'wake' :
                      'user';
  await initMemoryProvider({
    sessionId: sessionContext?.sessionId || 'default',
    sessionKind,
    channel: 'terminal',
    workspace: paths.root,
    piDir: paths.piDir,
  });

  initBackgroundManager();  // 初始化后台任务管理器

  cachedSkills = loadProjectSkills();

  const pluginRegistry = await loadPlugins(paths.pluginDirs);
  pluginTools = pluginRegistry.tools as any;

  if (pluginRegistry.records.length > 0) {
    console.log("🔌 插件加载完毕:");
    for (const r of pluginRegistry.records) {
      if (r.status === "loaded") {
        console.log(`  ✅ ${r.name}: ${r.toolCount} 工具, ${r.skillCount} 技能`);
      } else {
        console.warn(`  ❌ ${r.name}: ${r.error}`);
      }
    }
  }

  initSkillRouter(cachedSkills);
  initSkillsBlock(cachedSkills, pluginRegistry.skills);
  initSkillGuard(cachedSkills);

  cachedTools = getToolsForContext(sessionContext);

  // 初始化 plan tool 的工具上下文
  setPlanToolContext(cachedTools);

  baseInitialized = true;
}

/**
 * 核心 session 创建逻辑（内部复用）
 *
 * 自修复契约：
 * - services 创建失败 → 逐层降级（createServicesSafely，永不抛异常）
 * - 恢复文件缺失/损坏 → 自动回退全新会话（openSessionManagerSafely）
 * - 同一 sessionManager 的活跃会话 → 幂等复用（避免冷启动双建会话）
 *
 * @param sessionManagerOverride - 可选的 SessionManager（用于 /resume 切换 session）
 */
async function createSessionInternal(
  sessionManagerOverride?: unknown
): Promise<CreateSessionResult> {
  await initBaseOnce();

  // 幂等：相同 sessionManager 的活跃会话直接复用
  // （冷启动时 getSession 与 createAgentSessionRuntime 会各请求一次同一会话）
  if (session && sessionManagerOverride && (session as any).sessionManager === sessionManagerOverride) {
    return { session, services: sessionServices! } as CreateSessionResult;
  }

  // services 自修复创建（SDK 0.73+ 不再由 createAgentSession 返回）
  const services = await createServicesSafely(paths.root);
  sessionServices = services;

  // 恢复文件自修复：缺失/损坏时自动回退全新会话
  const sessionManager =
    sessionManagerOverride ??
    openSessionManagerSafely(sessionContext?.metadata?.sdkSessionFile);

  // @ts-ignore - Type mismatch from SDK update
  const result = await createAgentSession({
    cwd: paths.root,
    model: getLLM().getSessionModel() as any,
    sessionManager,
    resourceLoader: await createAppResourceLoader(paths.root),
    systemPrompt: () => buildSystemPromptForContext(sessionContext),
    customTools: cachedTools,
    skills: cachedSkills,
  } as any);

  session = result.session;
  normalizeAssistantUsages(session);
  initCompactTool(session);
  initRestartAgentTool(session);

  const sessionDir = getSessionDir();
  if (sessionDir) {
    initBrowserTool(sessionDir);
    initTaskTools(join(sessionDir, "tasks"));
    setSessionDataDir(sessionDir);
  }

  return {
    session: result.session,
    services,
    modelFallbackMessage: (result as any).modelFallbackMessage,
  } as CreateSessionResult;
}

/**
 * 暴露 session services（供 api/index.ts 构造 AgentSessionRuntime 使用）
 */
export function getSessionServices(): AgentSessionServices | null {
  return sessionServices;
}

/**
 * 为 AgentSessionRuntime 提供的 createRuntime 工厂函数
 * 当 /resume 切换 session 时，pi 框架会调用此工厂传入新的 SessionManager，
 * 我们需要基于这个 SessionManager 创建新的 AgentSession。
 */
export async function createRuntimeForSession(resumeOptions: {
  cwd: string;
  agentDir: string;
  sessionManager: unknown;
  sessionStartEvent?: unknown;
}): Promise<{
  session: AgentSession;
  services: AgentSessionServices;
  diagnostics: unknown[];
  modelFallbackMessage?: string;
}> {
  console.log(`🔄 正在恢复 session: ${(resumeOptions.sessionManager as any)?.getSessionFile?.() ?? "unknown"}`);
  // 统一走 createSessionInternal（幂等 + 自修复）；
  // services 由 createSessionInternal 内的 createServicesSafely 保证非空
  const result = await createSessionInternal(resumeOptions.sessionManager);
  const services =
    sessionServices ??
    (await createServicesSafely(resumeOptions.cwd, resumeOptions.agentDir));
  sessionServices = services;
  console.log(`✅ Session 恢复完成`);
  return {
    session: result.session,
    services,
    diagnostics: (services as any)?.diagnostics ?? [],
    modelFallbackMessage: (result as any).modelFallbackMessage,
  };
}

/**
 * 获取或创建 AgentSession（懒初始化，全局单例）
 */
export async function getSession(context?: SessionContext): Promise<AgentSession> {
  // 如果传入了新的 context，更新全局 context
  if (context) {
    sessionContext = context;
    console.log(`🔄 Session 上下文: ${context.type} (${context.sessionId})`);
  }

  if (!session) {
    try {
      const result = await createSessionInternal();
      session = result.session;
      // 注意：SDK 0.73+ 的 createAgentSession 不再返回 services，
      // sessionServices 已在 createSessionInternal 中赋值，此处不可覆盖。

      console.log(`📋 Session: ${getSessionKey()}`);

      logBootstrapFiles(getBootstrapData());
      logSystemPrompt(buildSystemPromptForContext(sessionContext), 0);

      try {
        const provider = getMemoryProvider();
        console.log(`🧠 记忆: ${provider.systemPromptBlock() || provider.name}`);
      } catch (error) {
        ErrorHandlers.silent(error, "获取记忆统计信息失败", undefined);
      }
    } catch (error) {
      handleAgentError(error, {
        context: "创建 AgentSession",
        severity: ErrorSeverity.FATAL,
        logStack: true,
        metadata: { sessionContext }
      });
      // session 创建失败是真正致命的（agent 无法工作），必须抛出让调用方明确失败，
      // 而不是返回 null 导致后续环节出现难以定位的二次崩溃
      throw error;
    }
  }
  return session!;
}

