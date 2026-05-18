import "dotenv/config";
import * as lark from "@larksuiteoapi/node-sdk";
import {
  SessionManager,
  estimateTokens,
  loadSkills,
  type Skill,
} from "@mariozechner/pi-coding-agent";
import { existsSync, mkdirSync } from "fs";
import { join } from "path";
import * as logger from "../infrastructure/logging/observable-logger.js";
import { createTrackedSession } from "../infrastructure/session/session-factory.js";
import { allCustomTools, initMemoryTools } from "../infrastructure/tools/index.js";
import type { ToolDefinition } from "../infrastructure/tools/index.js";
import { setPlanToolContext } from "../infrastructure/tools/plan-tool.js";
import { loadPlugins } from "../infrastructure/plugins/index.js";
import { createDeepSeekModel, paths } from "../config/config.js";
import {
  autoRecall,
  buildAgentSystemPrompt,
  initSkillsBlock,
  readDailyMemory,
} from "../core/agent/system-prompt.js";
import { microCompact, compactConversationHistory } from "../services/compaction/compaction-service.js";
import { initSkillGuard } from "../infrastructure/tools/skill-guard.js";
import { initSkillRouter } from "../services/intelligence/skill-router.js";
import { setSessionDataDir } from "../infrastructure/akshare-ts/shared.js";
import {
  FeishuSessionManager,
  type FeishuAgentSession,
} from "./feishu-session-manager.js";
import { CronService, type CronJobPayload } from "../services/operations/cron-service.js";
import {
  setSystemPrompt,
  getMessages,
  getMessageCount,
  hasState,
  addMessage,
  createUserMessage,
} from "../core/agent/session-adapter.js";

export interface FeishuBotHandle {
  shutdown: () => void;
}

const FEISHU_CRON_FILE = join(paths.piDir, "FEISHU_CRON.json");
const FEISHU_SESSIONS_DIR = join(paths.piDir, "sessions");
function ensurePiDir(): void {
  if (!existsSync(paths.piDir)) {
    mkdirSync(paths.piDir, { recursive: true });
  }
  if (!existsSync(FEISHU_SESSIONS_DIR)) {
    mkdirSync(FEISHU_SESSIONS_DIR, { recursive: true });
  }
}

function loadProjectSkills(): Skill[] {
  try {
    const result = loadSkills({ cwd: paths.root, skillPaths: [paths.skillsDir] });
    return result.skills;
  } catch (error) {
    console.warn("⚠️ Skills 加载失败:", error instanceof Error ? error.message : String(error));
    return [];
  }
}

function extractReply(session: FeishuAgentSession): string {
  const messages = getMessages(session);

  // Find the position of the last user message
  let lastUserIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "user") {
      lastUserIdx = i;
      break;
    }
  }
  if (lastUserIdx === -1) return "";

  // Collect all assistant messages after the last user message
  const texts: string[] = [];
  for (let i = lastUserIdx + 1; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.role !== "assistant" || !msg.content) continue;

    const text = msg.content
      .filter((block: any) => block.type === "text" && typeof block.text === "string")
      .map((block: any) => block.text ?? "")
      .join("\n")
      .trim();

    // Filter out short intermediate fragments (e.g. "Now let me record this.")
    if (text.length > 80) {
      texts.push(text);
    }
  }

  return texts.join("\n\n");
}

function parseTextMessage(content: string): string | null {
  try {
    const parsed = JSON.parse(content);
    return typeof parsed.text === "string" ? parsed.text.trim() : null;
  } catch {
    return null;
  }
}

async function sendReply(client: lark.Client, chatId: string, text: string): Promise<void> {
  // 飞书卡片 Markdown 内容限制约 30000 字符
  const MAX_CARD_LENGTH = 28000;
  let content = text;

  if (text.length > MAX_CARD_LENGTH) {
    content = text.substring(0, MAX_CARD_LENGTH) + "\n\n...\n\n⚠️ 内容过长已截断，完整内容请查看后续消息";
    console.warn(`⚠️ 飞书回复内容过长 (${text.length} 字符)，已截断至 ${MAX_CARD_LENGTH} 字符`);
  }

  const card = {
    config: {
      wide_screen_mode: true,
    },
    elements: [
      {
        tag: "markdown",
        content,
      },
    ],
    header: {
      template: "blue",
      title: {
        tag: "plain_text",
        content: "Pi Investment",
      },
    },
  };

  await client.im.message.create({
    params: { receive_id_type: "chat_id" },
    data: {
      receive_id: chatId,
      msg_type: "interactive",
      content: JSON.stringify(card),
    },
  });

  // 如果内容被截断，发送剩余部分
  if (text.length > MAX_CARD_LENGTH) {
    const remaining = text.substring(MAX_CARD_LENGTH);
    await sendReply(client, chatId, remaining);
  }
}

async function sendTextReply(client: lark.Client, chatId: string, text: string): Promise<void> {
  await client.im.message.create({
    params: { receive_id_type: "chat_id" },
    data: {
      receive_id: chatId,
      msg_type: "text",
      content: JSON.stringify({ text }),
    },
  });
}

export async function startFeishuBot(): Promise<FeishuBotHandle | null> {
  const appId = process.env.FEISHU_APP_ID;
  const appSecret = process.env.FEISHU_APP_SECRET;

  if (!appId || !appSecret) {
    console.warn("⚠️ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET，飞书 Bot 未启动");
    return null;
  }

  ensurePiDir();
  initMemoryTools(paths.piDir);

  const skills = loadProjectSkills();
  initSkillRouter(skills);
  initSkillGuard(skills);

  const pluginRegistry = await loadPlugins(paths.pluginDirs);
  initSkillsBlock(skills, pluginRegistry.skills);

  const feishuTools: ToolDefinition[] = [
    ...allCustomTools,
    ...pluginRegistry.tools,
  ];
  setPlanToolContext(feishuTools);

  const client = new lark.Client({
    appId,
    appSecret,
  });

  const sessionManager = new FeishuSessionManager({
    sessionsRootDir: FEISHU_SESSIONS_DIR,
    createSession: async (_chatId, sessionDir) => {
      const trackedSession = await createTrackedSession({
        agentType: "subagent",
        createOptions: {
          cwd: paths.root,
          sessionManager: SessionManager.continueRecent(paths.root, sessionDir),
          model: createDeepSeekModel(),
          systemPrompt: () => buildAgentSystemPrompt({
            memoryContext: "",
            dailyMemory: "",
            tools: feishuTools,
            workspaceDir: paths.root,
          }),
          customTools: feishuTools,
          skills,
        },
      });

      return trackedSession as unknown as FeishuAgentSession;
    },
    beforePrompt: async (session, _chatId, text, sessionDir) => {
      // 每次消息处理前，将数据输出目录指向当前 session
      if (sessionDir) setSessionDataDir(sessionDir);

      const memoryContext = autoRecall(text);
      const dailyMemory = readDailyMemory(paths.piDir);
      const systemPrompt = buildAgentSystemPrompt({
        memoryContext,
        dailyMemory,
        tools: feishuTools,
        workspaceDir: paths.root,
      });

      if (hasState(session)) {
        setSystemPrompt(session, systemPrompt);
        logger.logSystemPrompt(systemPrompt, getMessageCount(session));

        const messages = getMessages(session);
        microCompact(messages);

        const totalTokens = messages.reduce(
          (sum: number, message: unknown) => sum + estimateTokens(message as any),
          0
        );
        if (totalTokens > 40000) {
          compactConversationHistory(messages, (m: unknown) => estimateTokens(m as any), {
            keepTurns: 3,
            tokenThreshold: 40000,
          });

          // 对齐 CLI: 触发自动记忆保存
          console.log("🧠 触发自动记忆保存");
          await session.prompt(
            "Pre-compaction memory flush: Use memory_write to save important facts, " +
            "decisions, and context worth remembering across sessions. Be selective."
          );
        }

        // Detect retry loops: if the last 5+ consecutive tool results are all errors,
        // inject a stop instruction to prevent wasting context
        const recentToolErrors: Array<{ toolName: string }> = [];
        for (let i = messages.length - 1; i >= 0; i--) {
          const m = messages[i] as any;
          if (m.role === "toolResult") {
            if (m.isError) {
              recentToolErrors.unshift(m);
            } else {
              break;
            }
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
            `[系统提示] 以下工具连续失败 ${recentToolErrors.length} 次: ${failedTools}。请停止重试这些工具，基于已有数据直接给出分析结论，不要再调用这些失败的工具。`
          ));
        }
      }
    },
    extractReply,
  });

  const cronService = new CronService(
    FEISHU_CRON_FILE,
    paths.piDir,
    async (payload: CronJobPayload) => {
      if (payload.kind !== "agent_turn" || !payload.chatId || !payload.message) {
        return;
      }

      const reply = await sessionManager.processMessage(
        payload.chatId,
        `cron-${Date.now()}`,
        payload.message
      );

      if (reply) {
        await sendReply(client, payload.chatId, reply);
      }
    }
  );

  const dispatcher = new lark.EventDispatcher({}).register({
    "im.message.receive_v1": async (data: any) => {
      console.log("📨 收到飞书消息事件");
      const message = data?.message;
      if (!message || message.message_type !== "text") {
        console.log("⚠️ 消息类型不是 text，跳过");
        return;
      }

      if (sessionManager.isDuplicate(message.message_id)) {
        console.log(`⚠️ 检测到重复消息: ${message.message_id}`);
        return;
      }

      const text = parseTextMessage(message.content);
      if (!text) {
        return;
      }

      const chatId = message.chat_id;
      if (!chatId) {
        return;
      }

      if (text.toLowerCase() === "stop") {
        const aborted = await sessionManager.abort(chatId);
        await sendTextReply(client, chatId, aborted ? "已取消当前任务" : "当前没有运行中的任务");
        return;
      }

      await sendTextReply(
        client,
        chatId,
        sessionManager.isProcessing(chatId) ? "任务处理中，消息已排队" : "收到，正在处理"
      );

      try {
        const reply = await sessionManager.processMessage(chatId, message.message_id, text);
        if (reply) {
          await sendReply(client, chatId, reply);
        }
      } catch (error) {
        console.error("❌ 飞书消息处理失败:", error instanceof Error ? error.message : String(error));
        await sendTextReply(client, chatId, "抱歉，处理消息时出现错误，请稍后重试。");
      }
    },
    "im.message.message_read_v1": async () => {},
    "im.message.reaction.created_v1": async () => {},
    "im.chat.access_event.bot_p2p_chat_entered_v1": async () => {},
  });

  const wsClient = new lark.WSClient({
    appId,
    appSecret,
    loggerLevel: lark.LoggerLevel.error, // 降低日志级别，避免乱码输出
  });

  cronService.start();
  wsClient.start({ eventDispatcher: dispatcher });

  console.log("🤖 飞书 Bot 已启动（WebSocket 监听中）");
  console.log(`📁 会话目录: ${FEISHU_SESSIONS_DIR}`);

  const shutdown = () => {
    cronService.stop();
    sessionManager.shutdown();
  };

  return { shutdown };
}
