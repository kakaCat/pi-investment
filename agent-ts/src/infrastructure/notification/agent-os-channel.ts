/**
 * Agent OS Notification Channel
 *
 * 通过 Agent OS CLI 发送通知
 */

import type { Notification, NotificationChannel } from '../../services/notification/notification-service.js';
import { agentOSNotificationSend } from '../agent-os/cli.js';

export class AgentOSNotificationChannel implements NotificationChannel {
  readonly name = 'agent-os';
  private channelName: string;

  constructor(channelName: string = 'default') {
    this.channelName = channelName;
  }

  async send(notification: Notification): Promise<void> {
    try {
      const priority = this.mapLevelToPriority(notification.level);

      const result = await agentOSNotificationSend({
        channel: this.channelName,
        title: notification.title,
        content: notification.content,
        priority,
        metadata: notification.data,
      });

      if (!result.success) {
        throw new Error(result.error || 'Failed to send notification');
      }

      console.log(`[AgentOS Notification] Sent via channel '${this.channelName}': ${notification.title}`);
    } catch (error) {
      console.error(`[AgentOS Notification] Error:`, error);
      throw error;
    }
  }

  private mapLevelToPriority(level?: string): 'low' | 'medium' | 'high' | 'urgent' {
    switch (level) {
      case 'error':
        return 'urgent';
      case 'warning':
        return 'high';
      case 'success':
        return 'medium';
      case 'info':
      default:
        return 'low';
    }
  }
}

/**
 * 初始化 Agent OS Notification Channel
 */
export async function initAgentOSNotification(channelName: string = 'default'): Promise<AgentOSNotificationChannel> {
  return new AgentOSNotificationChannel(channelName);
}
