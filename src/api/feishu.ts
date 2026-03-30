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
import { microCompact } from "../services/compaction/compaction-service.js";
import { initSkillGuard } from "../services/intelligence/skill-guard.js";
import { initSkillRouter } from "../services/intelligence/skill-router.js";
import {
  FeishuSessionManager,
  type FeishuAgentSession,
} from "./feishu-session-manager.js";
import { CronService, type CronJobPayload } from "../services/cron/cron-service.js";

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;

if (!APP_ID || !APP_SECRET) {
  console.error("❌ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET");
  process.exit(1);
}

const FEISHU_CRON_FILE = join(paths.piDir, "FEISHU_CRON.json");
const FEISHU_SESSIONS_DIR = join(paths.piDir, "sessions");
const EXCLUDED_TOOLS = new Set([
  "compact",
  "browser",
  "task_create",
  "task_update",
  "task_list",
  "task_get",
  "task_execute_async",
  "task_check_background",
]);

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
  const messages = session.agent?.state?.messages ?? [];
  const lastAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  if (!lastAssistant?.content) {
    return "";
  }

  return lastAssistant.content
    .filter((block) => block.type === "text" && typeof block.text === "string")
    .map((block) => block.text ?? "")
    .join("\n")
    .trim();
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
  await client.im.message.create({
    params: { receive_id_type: "chat_id" },
    data: {
      receive_id: chatId,
      msg_type: "text",
      content: JSON.stringify({ text }),
    },
  });
}

async function main(): Promise<void> {
  ensurePiDir();
  logger.initSession();
  initMemoryTools(paths.piDir);
  const appId = APP_ID!;
  const appSecret = APP_SECRET!;

  const skills = loadProjectSkills();
  initSkillRouter(skills);
  initSkillGuard(skills);

  const pluginRegistry = await loadPlugins(paths.pluginDirs);
  initSkillsBlock(skills, pluginRegistry.skills);

  const feishuTools: ToolDefinition[] = [
    ...allCustomTools.filter((tool) => !EXCLUDED_TOOLS.has(tool.name)),
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
    beforePrompt: async (session, _chatId, text) => {
      const memoryContext = autoRecall(text);
      const dailyMemory = readDailyMemory(paths.piDir);
      const systemPrompt = buildAgentSystemPrompt({
        memoryContext,
        dailyMemory,
        tools: feishuTools,
        workspaceDir: paths.root,
      });

      if ((session as any).agent?.state) {
        (session as any).agent.state.systemPrompt = systemPrompt;
        microCompact((session as any).agent.state.messages);

        const totalTokens = ((session as any).agent.state.messages ?? []).reduce(
          (sum: number, message: unknown) => sum + estimateTokens(message as any),
          0
        );
        if (totalTokens > 40000) {
          console.warn("⚠️ Feishu session token 接近阈值，已执行微压缩");
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
      const message = data?.message;
      if (!message || message.message_type !== "text") {
        return;
      }

      if (sessionManager.isDuplicate(message.message_id)) {
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
        await sendReply(client, chatId, aborted ? "已取消当前任务。" : "当前没有运行中的任务。");
        return;
      }

      await sendReply(
        client,
        chatId,
        sessionManager.isProcessing(chatId) ? "任务处理中，消息已排队。" : "收到，正在处理。"
      );

      try {
        const reply = await sessionManager.processMessage(chatId, message.message_id, text);
        if (reply) {
          await sendReply(client, chatId, reply);
        }
      } catch (error) {
        console.error("❌ 飞书消息处理失败:", error instanceof Error ? error.message : String(error));
        await sendReply(client, chatId, "抱歉，处理消息时出现错误，请稍后重试。");
      }
    },
    "im.message.message_read_v1": async () => {},
    "im.chat.access_event.bot_p2p_chat_entered_v1": async () => {},
  });

  const wsClient = new lark.WSClient({
    appId,
    appSecret,
    loggerLevel: lark.LoggerLevel.info,
  });

  cronService.start();
  wsClient.start({ eventDispatcher: dispatcher });

  console.log("🚀 飞书 Bot 已启动");
  console.log(`📁 会话目录: ${FEISHU_SESSIONS_DIR}`);
  console.log(`⏰ Cron 配置: ${FEISHU_CRON_FILE}`);

  const shutdown = () => {
    cronService.stop();
    sessionManager.shutdown();
    logger.logSessionEnd();
    process.exit(0);
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

void main().catch((error) => {
  console.error("❌ 飞书 Bot 启动失败:", error instanceof Error ? error.message : String(error));
  process.exit(1);
});
