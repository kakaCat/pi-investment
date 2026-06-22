import { NotificationChannel, NotificationMessage } from './notification-channel.js';

/**
 * 通知选项
 */
export interface NotificationOptions {
  channel?: string;  // 渠道名称，默认使用第一个注册的渠道
  chatId?: string;   // 覆盖默认 chatId（飞书专用）
  priority?: 'low' | 'normal' | 'high';
}

/**
 * NotificationService - 统一通知服务
 *
 * 管理多个通知渠道，提供统一的发送接口
 */
export class NotificationService {
  private channels = new Map<string, NotificationChannel>();
  private defaultChannel: string | null = null;

  /**
   * 注册通知渠道
   */
  registerChannel(name: string, channel: NotificationChannel): void {
    this.channels.set(name, channel);
    if (this.defaultChannel === null) {
      this.defaultChannel = name;
    }
  }

  /**
   * 发送文本消息
   */
  async send(message: string, options?: NotificationOptions): Promise<void> {
    const notificationMessage: NotificationMessage = {
      content: message,
      type: 'text'
    };

    await this.sendToChannel(notificationMessage, options);
  }

  /**
   * 发送卡片消息
   */
  async sendCard(message: NotificationMessage, options?: NotificationOptions): Promise<void> {
    await this.sendToChannel(message, options);
  }

  /**
   * 发送图片
   */
  async sendImage(imageUrl: string, caption?: string, options?: NotificationOptions): Promise<void> {
    const channel = this.getChannel(options?.channel);
    if (!channel) {
      return;
    }

    if (!channel.isAvailable()) {
      console.warn(`[Notification] Channel ${options?.channel || this.defaultChannel} not available, skipping`);
      return;
    }

    await channel.sendImage(imageUrl, caption);
  }

  /**
   * 批量发送消息
   */
  async sendBatch(messages: NotificationMessage[], options?: NotificationOptions): Promise<void> {
    for (const message of messages) {
      await this.sendToChannel(message, options);
    }
  }

  /**
   * 内部方法：发送到指定渠道
   */
  private async sendToChannel(message: NotificationMessage, options?: NotificationOptions): Promise<void> {
    const channel = this.getChannel(options?.channel);
    if (!channel) {
      return;
    }

    if (!channel.isAvailable()) {
      console.warn(`[Notification] Channel ${options?.channel || this.defaultChannel} not available, skipping`);
      return;
    }

    await channel.send(message);
  }

  /**
   * 获取渠道实例
   */
  private getChannel(channelName?: string): NotificationChannel | null {
    const name = channelName || this.defaultChannel;
    if (!name) {
      console.warn('[Notification] No channel specified and no default channel registered');
      return null;
    }

    const channel = this.channels.get(name);
    if (!channel) {
      console.warn(`[Notification] Channel ${name} not found`);
      return null;
    }

    return channel;
  }
}
