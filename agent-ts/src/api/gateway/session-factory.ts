/**
 * 共享 Gateway 会话工厂
 * 从 feishu.ts / wake-channel.ts 抽取的公共会话创建与提示词准备逻辑
 */
import { estimateTokens, SessionManager, type Skill } from "../../sdk-facade.js";
import { createTrackedSession } from "../../infrastructure/session/session-factory.js";
import type { ToolDefinition } from "../../infrastructure/tools/index.js";
import { createModel, paths } from "../../config/config.js";
import { createAppResourceLoader } from "../extensions/model-command.js";
import {
  autoRecall,
  buildAgentSystemPrompt,
  readDailyMemory,
} from "../../core/agent/system-prompt.js";
import { setSessionDataDir } from "../../infrastructure/tools/shared/session-utils.js";
import {
  setSystemPrompt,
  getMessages,
  getMessageCount,
  hasState,
  addMessage,
  createUserMessage,
} from "../../core/agent/session-adapter.js";
import { microCompact, compactConversationHistory } from "../../services/compaction/compaction-service.js";
import * as logger from "../../infrastructure/logging/observable-logger.js";
import { setSessionContext } from "./session-events.js";
import type { ChannelAgentSession } from "./channel-session-manager.js";

export interface GatewaySessionFactory {
  createSession(sessionKey: string, sessionDir: string): Promise<ChannelAgentSession>;
  beforePrompt(session: ChannelAgentSession, sessionKey: string, text: string, sessionDir: string): Promise<void>;
}

/**
 * 提取回复：收集最后一条 user 消息之后的所有 assistant 长文本
 * （搬运自原 feishu.ts，过滤短中间片段）
 */
export function extractChannelReply(session: ChannelAgentSession): string {
  const messages = getMessages(session as any);

  let lastUserIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "user") {
      lastUserIdx = i;
      break;
    }
  }
  if (lastUserIdx === -1) return "";

  const texts: string[] = [];
  for (let i = lastUserIdx + 1; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.role !== "assistant" || !msg.content) continue;

    const content = Array.isArray(msg.content) ? msg.content : [];
    const text = content
      .filter((block: any) => block.type === "text" && typeof (block as any).text === "string")
      .map((block: any) => (block as any).text ?? "")
      .join("\n")
      .trim();

    // 过滤短中间片段（如 "Now let me record this."）
    if (text.length > 80) {
      texts.push(text);
    }
  }

  return texts.join("\n\n");
}

export function createGatewaySessionFactory(
  tools: ToolDefinition[],
  skills: Skill[],
): GatewaySessionFactory {
  return {
    createSession: async (_sessionKey, sessionDir) => {
      const trackedSession = await createTrackedSession({
        agentType: "subagent",
        createOptions: {
          cwd: paths.root,
          sessionManager: SessionManager.continueRecent(paths.root, sessionDir),
          model: createModel(),
          resourceLoader: await createAppResourceLoader(paths.root),
          systemPrompt: () => buildAgentSystemPrompt({
            memoryContext: "",
            dailyMemory: "",
            tools,
            workspaceDir: paths.root,
          }),
          customTools: tools,
          skills,
        },
      });
      return trackedSession as unknown as ChannelAgentSession;
    },

    beforePrompt: async (session, sessionKey, text, sessionDir) => {
      if (sessionDir) setSessionDataDir(sessionDir);
      setSessionContext(sessionKey, sessionDir);

      const memoryContext = autoRecall(text);
      const dailyMemory = readDailyMemory(paths.piDir);
      const systemPrompt = buildAgentSystemPrompt({
        memoryContext,
        dailyMemory,
        tools,
        workspaceDir: paths.root,
      });

      if (!hasState(session)) return;

      setSystemPrompt(session, systemPrompt);
      logger.logSystemPrompt(systemPrompt, getMessageCount(session));

      const messages = getMessages(session);
      microCompact(messages as any);

      const totalTokens = messages.reduce(
        (sum: number, message: unknown) => sum + estimateTokens(message as any),
        0,
      );
      if (totalTokens > 40000) {
        compactConversationHistory(messages as any, (m: unknown) => estimateTokens(m as any), {
          keepTurns: 3,
          tokenThreshold: 40000,
        });

        console.log("🧠 触发自动记忆保存");
        await session.prompt(
          "Pre-compaction memory flush: Use memory_write to save important facts, " +
          "decisions, and context worth remembering across sessions. Be selective.",
        );
      }

      // 工具重试死循环检测：最近 5+ 个连续 toolResult 全是错误时注入终止指令
      const recentToolErrors: Array<{ toolName: string }> = [];
      for (let i = messages.length - 1; i >= 0; i--) {
        const m = messages[i] as any;
        if (m.role === "toolResult") {
          if (m.isError) recentToolErrors.unshift(m);
          else break;
        } else if (m.role === "assistant") {
          continue;
        } else {
          break;
        }
      }
      if (recentToolErrors.length >= 5) {
        const failedTools = [...new Set(recentToolErrors.map((m: any) => m.toolName))].join(", ");
        console.warn(`⚠️ 检测到工具重试死循环: ${recentToolErrors.length} 次连续失败 (${failedTools})，注入终止指令`);
        addMessage(session, createUserMessage(
          `[系统提示] 以下工具连续失败 ${recentToolErrors.length} 次: ${failedTools}。请停止重试这些工具，基于已有数据直接给出分析结论，不要再调用这些失败的工具。`,
        ));
      }
    },
  };
}
