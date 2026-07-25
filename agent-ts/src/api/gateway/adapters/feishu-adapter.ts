/**
 * FeishuAdapter — 飞书通道（lark WSClient 长连接）
 * 只负责"翻译+传输"：飞书消息 ↔ InboundEvent
 */
import * as lark from "@larksuiteoapi/node-sdk";
import { join } from "path";
import { paths } from "../../../config/config.js";
// @ts-ignore - Module stub needed
import { CronService, type CronJobPayload } from "../../../services/operations/cron-service.js";
import { buildSessionKey } from "../session-key.js";
import { normalizeFeishuMessage } from "./feishu-normalize.js";
import type { ChannelAdapter, GatewayHandlers } from "../types.js";

export { normalizeFeishuMessage } from "./feishu-normalize.js";

const FEISHU_CRON_FILE = join(paths.piDir, "FEISHU_CRON.json");

export interface FeishuAdapterOptions {
  appId: string;
  appSecret: string;
}

export class FeishuAdapter implements ChannelAdapter {
  readonly name = "feishu";
  private client: lark.Client;
  private wsClient: lark.WSClient | null = null;
  private cronService: CronService | null = null;

  constructor(private options: FeishuAdapterOptions) {
    this.client = new lark.Client({ appId: options.appId, appSecret: options.appSecret });
  }

  start(handlers: GatewayHandlers): void {
    this.cronService = new CronService(
      FEISHU_CRON_FILE,
      paths.piDir,
      async (payload: CronJobPayload) => {
        if (payload.kind !== "agent_turn" || !payload.chatId || !payload.message) return;
        const reply = await handlers.dispatch({
          channel: "feishu",
          peerId: payload.chatId,
          messageId: `cron-${Date.now()}`,
          text: payload.message,
        });
        if (reply) await this.sendReply(payload.chatId, reply);
      },
    );

    const dispatcher = new lark.EventDispatcher({}).register({
      "im.message.receive_v1": async (data: any) => {
        console.log("📨 收到飞书消息事件");
        const inbound = normalizeFeishuMessage(data?.message);
        if (!inbound) return;

        if (inbound.text.toLowerCase() === "stop") {
          const aborted = await handlers.abort(buildSessionKey("feishu", inbound.peerId));
          await this.sendTextReply(inbound.peerId, aborted ? "已取消当前任务" : "当前没有运行中的任务");
          return;
        }

        const sessionKey = buildSessionKey("feishu", inbound.peerId);
        await this.sendTextReply(
          inbound.peerId,
          handlers.isProcessing(sessionKey) ? "任务处理中，消息已排队" : "收到，正在处理",
        );

        try {
          const reply = await handlers.dispatch(inbound);
          if (reply) await this.sendReply(inbound.peerId, reply);
        } catch (error) {
          console.error("❌ 飞书消息处理失败:", error instanceof Error ? error.message : String(error));
          await this.sendTextReply(inbound.peerId, "抱歉，处理消息时出现错误，请稍后重试。");
        }
      },
      "im.message.message_read_v1": async () => {},
      "im.message.reaction.created_v1": async () => {},
      "im.chat.access_event.bot_p2p_chat_entered_v1": async () => {},
    });

    this.wsClient = new lark.WSClient({
      appId: this.options.appId,
      appSecret: this.options.appSecret,
      loggerLevel: lark.LoggerLevel.error, // 降低日志级别，避免乱码输出
    });

    this.cronService.start();
    this.wsClient.start({ eventDispatcher: dispatcher });
    console.log("🤖 飞书 Bot 已启动（WebSocket 监听中）");
  }

  shutdown(): void {
    this.cronService?.stop();
  }

  private async sendTextReply(chatId: string, text: string): Promise<void> {
    await this.client.im.message.create({
      params: { receive_id_type: "chat_id" },
      data: {
        receive_id: chatId,
        msg_type: "text",
        content: JSON.stringify({ text }),
      },
    });
  }

  private async sendReply(chatId: string, text: string): Promise<void> {
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

    await this.client.im.message.create({
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
      await this.sendReply(chatId, remaining);
    }
  }
}
