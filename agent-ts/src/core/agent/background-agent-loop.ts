/**
 * Background Agent Loop - agent-loop 的分身
 *
 * 与 agent-loop 的区别：
 * - 注册了 spawn_background + check_background 工具
 * - 每次 prompt 前先 drain notification queue，把后台结果注入对话
 */
import {
  AgentSession,
  createAgentSession,
  loadSkills,
  type Skill
} from "@mariozechner/pi-coding-agent";
import type { Message } from "../../types/index.js";
import { compactTool } from "../../infrastructure/tools/agent/compact-tool.js";
import { taskCreateTool, taskUpdateTool, taskListTool, taskExecuteAsyncTool, taskCheckBackgroundTool, initTaskTools } from "../../infrastructure/tools/agent/task-tools.js";
import { microCompact } from "../../services/compaction/compaction-service.js";
import { initSkillGuard } from "../../infrastructure/tools/skill-guard.js";
import { initSkillRouter, rewritePromptWithSkill } from "../../services/intelligence/skill-router.js";
import { join } from "path";
import { SessionIdMapper } from "../session/session-id-mapper.js";
import { createDeepSeekModel, paths } from "../../config/config.js";
import { getAgentState, getLastMessage, extractTextContent } from "./session-adapter.js";
import { ErrorHandlers, handleAgentError, ErrorSeverity } from "./error-handler.js";

let session: AgentSession | null = null;

function loadProjectSkills(): Skill[] {
  try {
    // @ts-ignore - Type mismatch from SDK update
    const result = loadSkills({ cwd: paths.root, skillPaths: [join(paths.root, "skills")] });
    if ((result as any).warnings?.length > 0) {
      (result as any).warnings.forEach((w: any) => console.warn(`⚠️  ${w.skillPath}: ${w.message}`));
    }
    if (result.skills.length > 0) {
      console.log(`✅ 已加载 ${result.skills.length} 个 skills`);
    }
    return result.skills;
  } catch (error) {
    return ErrorHandlers.warn(error, "Background Agent Skills 加载失败", []);
  }
}

export async function getSession(): Promise<AgentSession> {
  if (!session) {
    const skills = loadProjectSkills();
    initSkillRouter(skills);
    initSkillGuard(skills);
    // @ts-ignore - Type mismatch from SDK update
    const result = await createAgentSession({
      cwd: paths.root,
      model: createDeepSeekModel(),
      systemPrompt: (defaultPrompt: any) => defaultPrompt,
      customTools: [
        taskExecuteAsyncTool,
        taskCheckBackgroundTool,
        compactTool,
        taskCreateTool, taskUpdateTool, taskListTool
      ],
      skills,
    } as any);
    session = result.session;

    const sessionUuid = session.sessionManager.getSessionId() || "default";
    const mapper = new SessionIdMapper(paths.sessionMapFile);
    const friendlySessionId = mapper.getFriendlyId(sessionUuid);
    console.log(`📋 Session: ${friendlySessionId} (${sessionUuid})`);

    const tasksDir = join(paths.sessionsDir, sessionUuid, "tasks");
    initTaskTools(tasksDir);
  }
  return session;
}

export async function agentLoop(messages: Message[]): Promise<void> {
  try {
    const agentSession = await getSession();

    const lastUserMessage = messages[messages.length - 1];
    if (lastUserMessage.role !== "user") return;

    const userContent = typeof lastUserMessage.content === "string"
      ? lastUserMessage.content
      : Array.isArray(lastUserMessage.content)
        ? lastUserMessage.content.find(c => typeof c === "object" && "text" in c)?.text || ""
        : "";

    if (!userContent.trim()) {
      console.warn("⚠️  用户消息为空，跳过处理");
      return;
    }

    const agentState = getAgentState(agentSession);
    if (agentState) {
      microCompact(agentState.messages);
    }

    const routed = rewritePromptWithSkill(userContent);
    if (routed.forcedSkill) {
      console.log(`🎯 强制技能路由: ${routed.forcedSkill}`);
    }

    await agentSession.prompt(routed.prompt);

    const lastMsg = getLastMessage(agentSession);

    if (lastMsg?.role === "assistant") {
      const textContent = extractTextContent(lastMsg);
      if (textContent) {
        messages.push({ role: "assistant", content: textContent });
      }
    }
  } catch (error) {
    handleAgentError(error, {
      context: "Background Agent 循环执行",
      severity: ErrorSeverity.FATAL,
      logStack: true,
      metadata: {
        messagesCount: messages.length,
        lastMessageRole: messages[messages.length - 1]?.role
      }
    });
  }
}
