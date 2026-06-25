/**
 * NotificationService - 通用通知服务
 * 支持多种通知渠道（飞书、邮件、Webhook等）
 */

export interface Notification {
  title: string;
  content: string;
  level?: 'info' | 'warning' | 'error' | 'success';
  data?: any;
}

export interface NotificationChannel {
  name: string;
  send: (notification: Notification) => Promise<void>;
}

export class NotificationService {
  private channels: Map<string, NotificationChannel> = new Map();

  /**
   * 注册通知渠道
   */
  registerChannel(channel: NotificationChannel): void {
    this.channels.set(channel.name, channel);
    console.log(`[NotificationService] 注册通知渠道: ${channel.name}`);
  }

  /**
   * 注销通知渠道
   */
  unregisterChannel(channelName: string): void {
    this.channels.delete(channelName);
    console.log(`[NotificationService] 注销通知渠道: ${channelName}`);
  }

  /**
   * 发送通知到指定渠道
   */
  async send(channelName: string, notification: Notification): Promise<void> {
    const channel = this.channels.get(channelName);
    if (!channel) {
      console.warn(`[NotificationService] 通知渠道不存在: ${channelName}`);
      return;
    }

    try {
      await channel.send(notification);
      console.log(`[NotificationService] 通知已发送到 ${channelName}: ${notification.title}`);
    } catch (error) {
      console.error(`[NotificationService] 发送通知失败 (${channelName}):`, error);
      throw error;
    }
  }

  /**
   * 广播通知到所有渠道
   */
  async broadcast(notification: Notification): Promise<void> {
    const results = await Promise.allSettled(
      Array.from(this.channels.values()).map(channel => channel.send(notification))
    );

    const failed = results.filter(r => r.status === 'rejected');
    if (failed.length > 0) {
      console.warn(`[NotificationService] ${failed.length} 个渠道发送失败`);
    }
  }

  /**
   * 发送卡片式通知到所有渠道（broadcast 别名）
   */
  async sendCard(message: { title: string; content: string; type?: string; metadata?: any }): Promise<void> {
    await this.broadcast({
      title: message.title,
      content: message.content,
      level: 'info',
      data: message.metadata,
    });
  }

  /**
   * 获取所有已注册的渠道
   */
  getChannels(): string[] {
    return Array.from(this.channels.keys());
  }

  /**
   * 检查渠道是否已注册
   */
  hasChannel(channelName: string): boolean {
    return this.channels.has(channelName);
  }
}

// 导出单例实例
export const notificationService = new NotificationService();
