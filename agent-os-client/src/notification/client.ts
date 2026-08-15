import { BaseHTTPClient } from '../http/client.js';
import {
  NotificationChannel,
  NotificationSendRequest,
  Notification,
  NotificationListFilters,
} from './types.js';

/**
 * Notification Client - Send notifications via various channels
 */
export class NotificationClient {
  constructor(private http: BaseHTTPClient) {}

  /**
   * Send a notification
   */
  async send(request: NotificationSendRequest): Promise<Notification> {
    return this.http.post<Notification>('/api/v1/notifications/send', request);
  }

  /**
   * List notification channels
   */
  async listChannels(): Promise<NotificationChannel[]> {
    return this.http.get<NotificationChannel[]>('/api/v1/notifications/channels');
  }

  /**
   * Get channel by ID
   */
  async getChannel(id: string): Promise<NotificationChannel> {
    return this.http.get<NotificationChannel>(`/api/v1/notifications/channels/${id}`);
  }

  /**
   * List notification history
   */
  async list(filters?: NotificationListFilters): Promise<Notification[]> {
    return this.http.get<Notification[]>('/api/v1/notifications', filters);
  }

  /**
   * Get notification by ID
   */
  async get(id: string): Promise<Notification> {
    return this.http.get<Notification>(`/api/v1/notifications/${id}`);
  }

  /**
   * Test a notification channel
   */
  async testChannel(channelId: string, testMessage?: string): Promise<{ success: boolean }> {
    return this.http.post(`/api/v1/notifications/channels/${channelId}/test`, {
      message: testMessage || 'Test notification from Agent OS',
    });
  }
}
