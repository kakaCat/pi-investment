/**
 * Gateway 共享启动引导：tools + skills + plugins + factory + gateway + syncer
 * Phase 1: 每个进程挂自己的 adapter；Phase 2: 单进程挂多个 adapter
 */
import { existsSync, mkdirSync } from "fs";
import { join } from "path";
import { loadSkills, type Skill } from "../../sdk-facade.js";
import { allCustomTools, initMemoryTools } from "../../infrastructure/tools/index.js";
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
  shutdown: () => Promise<void>;
}

export async function startGateway(adapters: ChannelAdapter[]): Promise<GatewayHandle> {
  initSessionEvents(join(paths.piDir, "agent-sessions"));
  const sessionsRootDir = getAgentSessionsRootDir();
  mkdirSync(sessionsRootDir, { recursive: true });

  initMemoryTools(paths.piDir);

  const skills = loadProjectSkills();
  initSkillRouter(skills);
  initSkillGuard(skills);

  const pluginRegistry = await loadPlugins(paths.pluginDirs);
  initSkillsBlock(skills, pluginRegistry.skills);

  const tools: ToolDefinition[] = [
    ...allCustomTools,
    ...pluginRegistry.tools as any[],
  ] as ToolDefinition[];
  console.log(`[Gateway] 已加载 ${tools.length} 个工具`);
  setPlanToolContext(tools);

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
  for (const adapter of adapters) {
    adapter.start(handlers);
  }
  console.log(`[Gateway] 已启动 ${adapters.length} 个通道: ${adapters.map((a) => a.name).join(", ")}`);
  console.log(`📁 会话目录: ${sessionsRootDir}`);

  return {
    gateway,
    shutdown: async () => {
      for (const adapter of adapters) adapter.shutdown();
      gateway.shutdown();
      await syncer.stop();
    },
  };
}
