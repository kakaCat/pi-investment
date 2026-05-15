/**
 * 通知消息结构
 */
export interface NotificationMessage {
  title?: string;
  content: string;
  type: 'text' | 'markdown' | 'card';
  metadata?: Record<string, any>;
}

/**
 * NotificationChannel 抽象基类
 *
 * 所有通知渠道（飞书、钉钉、邮件等）必须继承此类并实现其方法
 */
export abstract class NotificationChannel {
  /**
   * 发送消息
   */
  abstract send(message: NotificationMessage): Promise<void>;

  /**
   * 发送图片
   */
  abstract sendImage(imageUrl: string, caption?: string): Promise<void>;

  /**
   * 检查渠道是否可用（配置是否完整）
   */
  abstract isAvailable(): boolean;
}
