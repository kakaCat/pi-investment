/**
 * Background Agent Session - agent-loop 的分身
 *
 * 与 agent-loop 的区别：
 * - 注册了 spawn_background + check_background 工具
 *
 * 注：本文件原有的 agentLoop 消息循环无调用方，2026-08-12 作为死代码删除
 * （其中的技能路由调用曾误导审计；生产消息循环在 gateway channel-session-manager）。
 */
import {
  AgentSession,
  createAgentSession,
  loadSkills,
  type Skill
} from "../../sdk-facade.js";
import { compactTool } from "../../infrastructure/tools/agent/compact-tool.js";
import { taskCreateTool, taskUpdateTool, taskListTool, taskExecuteAsyncTool, taskCheckBackgroundTool, initTaskTools } from "../../infrastructure/tools/agent/task-tools.js";
import { initSkillGuard } from "../../infrastructure/tools/skill-guard.js";
import { initSkillRouter } from "../../services/intelligence/skill-router.js";
import { join } from "path";
import { SessionIdMapper } from "../session/session-id-mapper.js";
import { paths } from "../../config/config.js";
import { getLLM } from "../../services/llm/index.js";
import { createAppResourceLoader } from "../../api/extensions/model-command.js";
import { ErrorHandlers } from "./error-handler.js";

let session: AgentSession | null = null;

function loadProjectSkills(): Skill[] {
  try {
    // @ts-ignore - Type mismatch from SDK update
    const result = loadSkills({ cwd: paths.root, skillPaths: [join(paths.root, "skills")] } as any);
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
      model: getLLM().getSessionModel() as any,
      resourceLoader: await createAppResourceLoader(paths.root),
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
  return session!;
}
