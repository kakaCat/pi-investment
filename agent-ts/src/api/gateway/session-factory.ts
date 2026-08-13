/**
 * 共享 Gateway 会话工厂
 * 从 feishu.ts / wake-channel.ts 抽取的公共会话创建与提示词准备逻辑
 * T3b 接线: beforePrompt 应用 tool result TTL 策略
 */
import { estimateTokens, SessionManager, type Skill } from "../../sdk-facade.js";
import { createTrackedSession } from "../../infrastructure/session/session-factory.js";
import type { ToolDefinition } from "../../infrastructure/tools/index.js";
import { paths } from "../../config/config.js";
import { getLLM, getSessionModelFor } from "../../services/llm/index.js";
import { selectToolsForKind } from "../../domain/agent-roles/assembly.js";
import { getProfile } from "../../domain/agent-roles/profiles.js";
import type { AgentKind } from "../../domain/agent-roles/types.js";
import { createLazyModelSync } from "./llm-lazy-sync.js";
import { createAppResourceLoader } from "../extensions/model-command.js";
import {
  autoRecall,
  buildAgentSystemPrompt,
  readDailyMemory,
} from "../../core/agent/system-prompt.js";
import { setSessionDataDir } from "../../infrastructure/tools/shared/session-utils.js";
import { isToolSearchMode } from "../../infrastructure/tools/catalog.js";
import {
  getMessages,
  hasState,
  addMessage,
  createUserMessage,
} from "../../core/agent/session-adapter.js";
import { microCompact, compactConversationHistory } from "../../services/compaction/compaction-service.js";
import { applyToolResultTTL } from "../../services/compaction/tool-result-ttl.js";
import { parseSessionKey } from "./session-key.js";

/**
 * A3-T1 渠道接线：从 sessionKey（agent:<agentId>:<channel>:<peerId>）提取渠道，
 * 映射到提示词 Channel 层。feishu/web 有专属 hint；其余（wake/terminal 等）走 terminal 默认。
 * 解析失败（非标准 key）不抛——Channel 层只是语气提示，绝不阻断会话创建。
 */
export function channelHintFromSessionKey(
  sessionKey: string,
): "terminal" | "api" | "feishu" | "tui" | "web" {
  try {
    const { channel } = parseSessionKey(sessionKey);
    if (channel === "feishu" || channel === "web" || channel === "tui" || channel === "api") {
      return channel;
    }
    return "terminal";
  } catch {
    return "terminal";
  }
}
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
  agentKind: AgentKind = 'fin',
): GatewaySessionFactory {
  const lazyModelSync = createLazyModelSync({
    getVersion: () => getLLM().current().version,
    getSessionModel: () => getLLM().getSessionModel(),
  });
  // fin 等价性铁律：fin 不过滤工具（现状全集，零变化）；其余按 profile 过滤。
  const sessionTools = agentKind === 'fin' ? tools : selectToolsForKind(agentKind, tools);
  return {
    createSession: async (_sessionKey, sessionDir) => {
      const trackedSession = await createTrackedSession({
        agentType: "subagent",
        createOptions: {
          cwd: paths.root,
          sessionManager: SessionManager.continueRecent(paths.root, sessionDir),
          model: getSessionModelFor(getProfile(agentKind).modelPreference) as any,
          // SDK createAgentSession 静默忽略 systemPrompt 选项——系统提示词只能经 resourceLoader.getSystemPrompt() 注入。
          // 会话创建时快照当日记忆（beforePrompt 不再每轮重建系统提示词——W2.5 缓存修复）
          resourceLoader: await createAppResourceLoader(
            paths.root,
            buildAgentSystemPrompt({
              memoryContext: "",
              dailyMemory: readDailyMemory(paths.piDir),
              tools: sessionTools,
              workspaceDir: paths.root,
              toolSearchMode: isToolSearchMode(),
              agentKind,
              channel: channelHintFromSessionKey(_sessionKey),
            })
          ),
          customTools: sessionTools,
          skills,
        },
      });
      return trackedSession as unknown as ChannelAgentSession;
    },

    beforePrompt: async (session, sessionKey, text, sessionDir) => {
      if (sessionDir) setSessionDataDir(sessionDir);
      setSessionContext(sessionKey, sessionDir);
      lazyModelSync(session, sessionKey);

      // W2.5 修复（2026-08-13 审计实证）：此前每轮 rebuild + setSystemPrompt，
      // 且把 autoRecall(text)/dailyMemory 嵌进系统提示词——召回内容每条消息都不同，
      // 系统提示词每轮变化 → 64-token 块前缀从第 0 位断裂 → 整轮 cacheRead=0
      // （wake 会话 08-12 02:00 运行 30 轮全程零命中，51K→91K 全价支付）。
      // 系统提示词只在 createSession 构建一次（窄腰原则）；
      // 召回内容改为消息级注入：append 到消息流尾部（append-only 保前缀）。
      if (hasState(session)) {
        const recalled = autoRecall(text);
        if (recalled) {
          addMessage(session, createUserMessage(
            `<recalled_memory source="auto-recall">\n${recalled}\n</recalled_memory>`,
          ));
        }
      }

      const messages = getMessages(session);
      microCompact(messages as any);

      // T3b 接线：应用 Tool Result TTL 策略（20 轮 / 0.5×窗口预算）
      try {
        await applyToolResultTTL(messages as any, {
          maxTurns: 20,
          maxBudgetRatio: 0.5,
          contextWindowSize: 128000, // DeepSeek v4 默认
        });
      } catch (ttlErr) {
        console.warn(`⚠️ Tool result TTL 应用失败: ${ttlErr instanceof Error ? ttlErr.message : String(ttlErr)}`);
      }

      const totalTokens = messages.reduce(
        (sum: number, message: unknown) => sum + estimateTokens(message as any),
        0,
      );
      if (totalTokens > 40000) {
        // 2026-08-12 修补：先落盘记忆再压缩（OpenClaw 模式）——压缩后内容已丢失，
        // 之前 flush 在 compact 之后执行，抢救不到任何内容
        console.log("🧠 触发压缩前记忆落盘");
        await session.prompt(
          "Pre-compaction memory flush: Use memory_write to save important facts, " +
          "decisions, and context worth remembering across sessions. Be selective.",
        );

        // T3 接线：传入 memoryProvider 触发压缩前 syncTurn 钩子（可选，未初始化不影响压缩）
        let memoryProvider;
        try {
          const { getMemoryProvider } = await import("../../services/memory/index.js");
          memoryProvider = getMemoryProvider();
        } catch {
          memoryProvider = undefined;
        }

        compactConversationHistory(messages as any, (m: unknown) => estimateTokens(m as any), {
          keepTurns: 3,
          tokenThreshold: 40000,
          memoryProvider,
        });
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
