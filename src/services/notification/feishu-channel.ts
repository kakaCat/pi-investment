import * as lark from '@larksuiteoapi/node-sdk';
import { NotificationChannel, NotificationMessage } from './notification-channel.js';

export interface FeishuChannelConfig {
  appId: string;
  appSecret: string;
  defaultChatId: string;
}

/**
 * FeishuChannel - 飞书通知渠道实现
 */
export class FeishuChannel extends NotificationChannel {
  private client: lark.Client;
  private defaultChatId: string;
  private config: FeishuChannelConfig;

  constructor(config: FeishuChannelConfig) {
    super();
    this.config = config;
    this.client = new lark.Client({
      appId: config.appId,
      appSecret: config.appSecret
    });
    this.defaultChatId = config.defaultChatId;
  }

  isAvailable(): boolean {
    return !!(this.config.appId && this.config.appSecret && this.defaultChatId);
  }

  async send(message: NotificationMessage, chatId?: string): Promise<void> {
    const targetChatId = chatId || this.defaultChatId;

    if (message.type === 'card') {
      await this.sendCard(message, targetChatId);
    } else {
      await this.sendText(message.content, targetChatId);
    }
  }

  async sendImage(imageUrl: string, caption?: string, chatId?: string): Promise<void> {
    const targetChatId = chatId || this.defaultChatId;
    const card = this.buildImageCard(imageUrl, caption);

    await this.client.im.message.create({
      params: { receive_id_type: 'chat_id' },
      data: {
        receive_id: targetChatId,
        msg_type: 'interactive',
        content: JSON.stringify(card)
      }
    });
  }

  private async sendText(text: string, chatId: string): Promise<void> {
    await this.client.im.message.create({
      params: { receive_id_type: 'chat_id' },
      data: {
        receive_id: chatId,
        msg_type: 'text',
        content: JSON.stringify({ text })
      }
    });
  }

  private async sendCard(message: NotificationMessage, chatId: string): Promise<void> {
    const MAX_CARD_LENGTH = 28000;
    let content = message.content;

    if (content.length > MAX_CARD_LENGTH) {
      // 分片发送
      const firstPart = content.substring(0, MAX_CARD_LENGTH);
      const remaining = content.substring(MAX_CARD_LENGTH);

      const card = this.buildCard(message.title || 'Pi Investment', firstPart + '\n\n⚠️ 内容过长已截断');
      await this.client.im.message.create({
        params: { receive_id_type: 'chat_id' },
        data: {
          receive_id: chatId,
          msg_type: 'interactive',
          content: JSON.stringify(card)
        }
      });

      // 递归发送剩余部分
      await this.sendCard({ ...message, content: remaining }, chatId);
    } else {
      const card = this.buildCard(message.title || 'Pi Investment', content);
      await this.client.im.message.create({
        params: { receive_id_type: 'chat_id' },
        data: {
          receive_id: chatId,
          msg_type: 'interactive',
          content: JSON.stringify(card)
        }
      });
    }
  }

  private buildCard(title: string, content: string): any {
    return {
      config: {
        wide_screen_mode: true
      },
      elements: [
        {
          tag: 'markdown',
          content
        }
      ],
      header: {
        template: 'blue',
        title: {
          tag: 'plain_text',
          content: title
        }
      }
    };
  }

  private buildImageCard(imageUrl: string, caption?: string): any {
    const elements: any[] = [
      {
        tag: 'img',
        img_key: imageUrl,
        alt: {
          tag: 'plain_text',
          content: caption || 'Image'
        }
      }
    ];

    if (caption) {
      elements.push({
        tag: 'markdown',
        content: caption
      });
    }

    return {
      config: {
        wide_screen_mode: true
      },
      elements,
      header: {
        template: 'blue',
        title: {
          tag: 'plain_text',
          content: 'Pi Investment'
        }
      }
    };
  }
}
