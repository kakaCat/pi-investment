/**
 * 调度任务会话工厂 —— 按 agentKind 装配 Agent 会话。
 *
 * A2-T2：weekly_evolution 迁移为 evolution Agent 的 agent_turn 后，调度器的
 * promptAgent 需要能按任务指定的 agentKind 建对应身份的会话：
 *   - fin：保持现状裸会话（无 customTools / 无显式 model）——零变化（fin 等价性铁律）。
 *   - evolution/memory：装配对应工具组 + 档位模型 + 身份系统提示词。
 *
 * 系统提示词经 resourceLoader.getSystemPrompt() 注入（SDK 忽略 createAgentSession
 * 的 systemPrompt 选项），与 session-factory.ts 同源但走正确的注入通道。
 */
import { createSession } from "../../session-facade.js";
import { allCustomTools } from "../../infrastructure/tools/index.js";
import { selectToolsForKind } from "../../domain/agent-roles/assembly.js";
import { getProfile } from "../../domain/agent-roles/profiles.js";
import type { AgentKind } from "../../domain/agent-roles/types.js";
import { getSessionModelFor } from "../llm/index.js";
import { buildAgentSystemPrompt } from "../../core/agent/system-prompt.js";
import { createAppResourceLoader } from "../../api/extensions/model-command.js";
import { paths } from "../../config/config.js";

export async function createSchedulerSession(agentKind: AgentKind = "fin") {
  if (agentKind === "fin") {
    // fin 等价性铁律：调度任务的 fin 会话保持现状裸会话，零变化。
    return createSession({
      cwd: paths.root,
      resourceLoader: await createAppResourceLoader(paths.root),
    });
  }

  const tools = selectToolsForKind(agentKind, allCustomTools);
  const systemPrompt = buildAgentSystemPrompt({
    tools,
    workspaceDir: paths.root,
    agentKind,
  });

  return createSession({
    cwd: paths.root,
    model: getSessionModelFor(getProfile(agentKind).modelPreference),
    resourceLoader: await createAppResourceLoader(paths.root, systemPrompt),
    customTools: tools,
  });
}
