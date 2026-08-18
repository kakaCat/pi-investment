/**
 * Gateway 共享启动引导：tools + skills + plugins + factory + gateway + syncer
 * Phase 1: 每个进程挂自己的 adapter；Phase 2: 单进程挂多个 adapter
 *
 * WP-13: 支持多个 adapter 共享同一个 Express app 和端口
 */
import { existsSync, mkdirSync } from "fs";
import { join } from "path";
import express, { type Express } from "express";
import cors from "cors";
import { loadSkills, type Skill } from "../../sdk-facade.js";
import { allCustomTools, initMemoryTools } from "../../infrastructure/tools/index.js";
import { getCoreTools, isToolSearchMode } from "../../infrastructure/tools/catalog.js";
import { toolSearchMetaTools } from "../../infrastructure/tools/meta/tool-search-tools.js";
import type { ToolDefinition } from "../../infrastructure/tools/index.js";
import { setPlanToolContext } from "../../infrastructure/tools/agent/plan-tool.js";
import { loadPlugins } from "../../infrastructure/plugins/index.js";
import { initSkillGuard } from "../../infrastructure/tools/skill-guard.js";
import { initSkillRouter } from "../../services/intelligence/skill-router.js";
import { initSkillsBlock } from "../../core/agent/system-prompt.js";
import { paths } from "../../config/config.js";
import { AgentGateway } from "./gateway.js";
import { createGatewaySessionFactory, extractChannelReply } from "./session-factory.js";
import { SessionSyncer } from "./session-syncer.js";
import { initSessionEvents, getAgentSessionsRootDir } from "./session-events.js";
import type { ChannelAdapter } from "./types.js";
import type { Server } from "http";

function loadProjectSkills(): Skill[] {
  try {
    // @ts-ignore - Type mismatch from SDK update
    const result = loadSkills({
      cwd: paths.root,
      skillPaths: [paths.skillsDir],
      agentDir: paths.root,
      includeDefaults: true,
    });
    return result.skills;
  } catch (error) {
    console.warn("⚠️ Skills 加载失败:", error instanceof Error ? error.message : String(error));
    return [];
  }
}

export interface GatewayHandle {
  gateway: AgentGateway;
  server?: Server;  // HTTP 服务器（如果共享端口）
  shutdown: () => Promise<void>;
}

/**
 * 启动 Gateway，支持多个 adapter 共享端口
 *
 * @param adapters - Channel adapters (Wake, Agent OS, etc.)
 * @param options - 启动选项
 * @param options.sharedPort - 共享端口号（如果需要多个 adapter 共享）
 */
export async function startGateway(
  adapters: ChannelAdapter[],
  options?: { sharedPort?: number }
): Promise<GatewayHandle> {
  initSessionEvents(join(paths.piDir, "agent-sessions"));
  const sessionsRootDir = getAgentSessionsRootDir();
  mkdirSync(sessionsRootDir, { recursive: true });

  initMemoryTools(paths.piDir);

  const skills = loadProjectSkills();
  initSkillRouter(skills);
  initSkillGuard(skills);

  const pluginRegistry = await loadPlugins(paths.pluginDirs);
  initSkillsBlock(skills, pluginRegistry.skills);

  const tools: ToolDefinition[] = isToolSearchMode()
    ? [...getCoreTools(), ...toolSearchMetaTools, ...pluginRegistry.tools as any[]] as ToolDefinition[]
    : [
        ...allCustomTools,
        ...pluginRegistry.tools as any[],
      ] as ToolDefinition[];
  console.log(`[Gateway] 已加载 ${tools.length} 个工具（tool_search=${isToolSearchMode() ? "on" : "off"}）`);
  // plan 子代理始终拿全量注册表（不经 Tool Search）
  setPlanToolContext([...allCustomTools, ...pluginRegistry.tools as any[]] as ToolDefinition[]);

  const factory = createGatewaySessionFactory(tools, skills);
  const gateway = new AgentGateway({
    sessionsRootDir,
    createSession: factory.createSession,
    beforePrompt: factory.beforePrompt,
    extractReply: (session) => extractChannelReply(session),
  });

  const syncer = new SessionSyncer({
    apiBase: process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001",
    sessionsRootDir,
  });
  syncer.start();

  const handlers = gateway.handlers();

  // 如果指定了共享端口，创建共享的 Express app
  let sharedApp: Express | undefined;
  let server: Server | undefined;

  if (options?.sharedPort) {
    sharedApp = express();
    sharedApp.use(cors({ origin: process.env.CORS_ORIGIN || "*" }));
    sharedApp.use(express.json());

    console.log(`[Gateway] 创建共享 HTTP 服务器 (端口 ${options.sharedPort})`);
  }

  // 启动所有 adapters
  for (const adapter of adapters) {
    // 如果 adapter 支持共享 app (有 startShared 方法)
    if ('startShared' in adapter && typeof adapter.startShared === 'function') {
      if (sharedApp) {
        (adapter as any).startShared(handlers, sharedApp);
      } else {
        adapter.start(handlers);
      }
    } else {
      adapter.start(handlers);
    }
  }

  // 如果有共享 app，启动服务器
  if (sharedApp && options?.sharedPort) {
    server = sharedApp.listen(options.sharedPort, () => {
      console.log(`🌐 Gateway HTTP 服务器启动: http://127.0.0.1:${options.sharedPort}`);
    });
  }

  console.log(`[Gateway] 已启动 ${adapters.length} 个通道: ${adapters.map((a) => a.name).join(", ")}`);
  console.log(`📁 会话目录: ${sessionsRootDir}`);

  return {
    gateway,
    server,
    shutdown: async () => {
      if (server) {
        await new Promise<void>((resolve) => {
          server!.close(() => resolve());
        });
      }
      for (const adapter of adapters) adapter.shutdown();
      gateway.shutdown();
      await syncer.stop();
    },
  };
}
