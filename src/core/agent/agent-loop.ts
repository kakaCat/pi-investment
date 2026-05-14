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
  estimateTokens
} from "@mariozechner/pi-coding-agent";
import type { Message } from "../../types/index.js";
import { allCustomTools, initCompactTool, initBrowserTool, initTaskTools, initMemoryTools, initBackgroundManager, getBackgroundManager } from "../../infrastructure/tools/index.js";
import type { ToolDefinition } from "../../infrastructure/tools/index.js";
import { setPlanToolContext } from "../../infrastructure/tools/plan-tool.js";
import { loadPlugins } from "../../infrastructure/plugins/index.js";
import { getMemoryStore } from "../../services/intelligence/memory-store.js";
import { microCompact } from "../../services/compaction/compaction-service.js";
import { join } from "path";
import { createDeepSeekModel, paths } from "../../config/config.js";
import { getSessionDir, getSessionKey, logSystemPrompt, logBootstrapFiles } from "../../infrastructure/logging/observable-logger.js";
import { initSkillsBlock, autoRecall, readDailyMemory, buildAgentSystemPrompt } from "./system-prompt.js";
import { getBootstrapData } from "../../config/config.js";
import { initSkillRouter, rewritePromptWithSkill } from "../../services/intelligence/skill-router.js";
import {
  addMessage,
  createUserMessage,
  createAssistantMessage,
  setSystemPrompt,
  getMessages,
  getMessageCount,
  getLastMessage,
  extractTextContent,
  getAgentState,
} from "./session-adapter.js";

// 全局会话实例，复用同一个 session
let session: AgentSession | null = null;
// 插件贡献的工具（在 getSession 中初始化）
let pluginTools: ToolDefinition[] = [];

/** 返回内置工具 + 插件工具的合并列表 */
function getEffectiveTools(): ToolDefinition[] {
  return [...allCustomTools, ...pluginTools];
}

/**
 * 加载项目中的 skills，打印加载结果
 */
function loadProjectSkills(): Skill[] {
  try {
    const result = loadSkills({ cwd: paths.root, skillPaths: [join(paths.root, "skills")] });

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
    console.warn("⚠️  Skills 加载失败:", error instanceof Error ? error.message : String(error));
    return [];
  }
}

/**
 * 获取或创建 AgentSession（懒初始化，全局单例）
 */
export async function getSession(): Promise<AgentSession> {
  if (!session) {
    try {
      initMemoryTools(paths.piDir);
      initBackgroundManager();  // 初始化后台任务管理器

      const skills = loadProjectSkills();

      const pluginRegistry = await loadPlugins(paths.pluginDirs);
      pluginTools = pluginRegistry.tools;

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

      initSkillRouter(skills);
      initSkillsBlock(skills, pluginRegistry.skills);

      const effectiveTools = getEffectiveTools();

      // 初始化 plan tool 的工具上下文
      setPlanToolContext(effectiveTools);

      const result = await createAgentSession({
        cwd: paths.root,
        model: createDeepSeekModel(),
        systemPrompt: () => buildAgentSystemPrompt({
          memoryContext: "",
          dailyMemory: "",
          tools: getEffectiveTools(),
          workspaceDir: paths.root,
        }),
        customTools: effectiveTools,
        skills,
      } as any);
      session = result.session;
      initCompactTool(session);

      const sessionDir = getSessionDir();
      initBrowserTool(sessionDir);
      console.log(`📋 Session: ${getSessionKey()}`);

      logBootstrapFiles(getBootstrapData());
      logSystemPrompt(buildAgentSystemPrompt({
        memoryContext: "",
        dailyMemory: "",
        tools: effectiveTools,
        workspaceDir: paths.root,
      }), 0);

      initTaskTools(join(sessionDir, "tasks"));

      try {
        const stats = getMemoryStore().getStats();
        console.log(`🧠 记忆: 长期 ${stats.evergreenChars} 字符, ${stats.dailyFiles} 个每日文件 (${stats.dailyEntries} 条)`);
      } catch { /* ignore */ }

    } catch (error) {
      console.error("❌ 创建 AgentSession 失败:", error instanceof Error ? error.message : String(error));
      throw error;
    }
  }
  return session;
}

/**
 * Agent 循环主函数
 */
export async function agentLoop(messages: Message[]): Promise<void> {
  try {
    const agentSession = await getSession();

    // ============================================================
    // 并行工具调用机制：注入后台任务完成通知
    // ============================================================
    // 工作原理：
    // 1. Agent 上一轮调用了 background_run(taskId, toolName, params)
    // 2. 工具在 Worker 线程中异步执行，不阻塞 Agent
    // 3. 本轮开始时，drainNotifications() 获取所有已完成的任务
    // 4. 将结果注入到 Agent 的消息历史中（作为 <background-results>）
    // 5. Agent 看到结果后继续分析，或启动下一批并行任务
    //
    // 这样实现了真正的并行：
    // - 上一轮：启动 3 个 background_run → 立即返回
    // - 本轮：收到 3 个任务的结果 → 继续工作
    // ============================================================
    const bgManager = getBackgroundManager();
    const notifications = bgManager.drainNotifications();

    if (notifications.length > 0) {
      const notifText = notifications
        .map(n => `[Task #${n.taskId}] ${n.status} (${Math.round(n.duration/1000)}s):\n${JSON.stringify(n.result).slice(0, 500)}`)
        .join("\n\n");

      addMessage(agentSession, createUserMessage(`<background-results>\n${notifText}\n</background-results>`));
      addMessage(agentSession, createAssistantMessage("Noted background results."));

      console.log(`📬 注入 ${notifications.length} 个后台任务结果`);
    }

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

    const memoryContext = autoRecall(userContent);
    if (memoryContext) console.log("  🧠 [自动召回] 找到相关记忆");

    const dailyMemory = readDailyMemory(paths.piDir);

    // 每轮重建系统提示词（记忆可能在上一轮被更新）
    const newSystemPrompt = buildAgentSystemPrompt({
      memoryContext,
      dailyMemory,
      tools: getEffectiveTools(),
      workspaceDir: paths.root,
    });
    setSystemPrompt(agentSession, newSystemPrompt);
    logSystemPrompt(newSystemPrompt, getMessageCount(agentSession));

    const agentState = getAgentState(agentSession);
    if (agentState) {
      microCompact(agentState.messages);
    }

    // 自动记忆保存：接近上下文窗口时触发
    const totalTokens = getMessages(agentSession).reduce(
      (sum, msg) => sum + estimateTokens(msg), 0
    );
    if (totalTokens > 40000) {
      console.log("🧠 触发自动记忆保存");
      await agentSession.prompt(
        "Pre-compaction memory flush: Use memory_write to save important facts, " +
        "decisions, and context worth remembering across sessions. Be selective."
      );
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

    // 如果有后台任务运行，等待完成后继续循环
    const runningCount = bgManager.getRunningCount();
    if (runningCount > 0) {
      console.log(`⏳ 等待 ${runningCount} 个后台任务完成...`);
      await new Promise(resolve => setTimeout(resolve, 2000));
      // 递归调用，继续处理
      return agentLoop(messages);
    }
  } catch (error) {
    console.error("❌ Agent 循环执行失败:", error instanceof Error ? error.message : String(error));
    throw error;
  }
}
