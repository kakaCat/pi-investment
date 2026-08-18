import { AxiosInstance } from 'axios';
import { createHttpClient } from './http.js';
import type {
  RegistryClientConfig,
  SendNotificationParams,
  SendNotificationResponse,
} from './types.js';

/**
 * NotificationClient — Agent OS notification APIs.
 *
 * Server contract (verified live):
 *   POST /api/v1/notifications/send   (SendNotificationRequest: channel/title/content)
 *   GET  /api/v1/notifications/channels
 *   GET  /api/v1/notifications/providers
 *   GET  /api/v1/notifications/logs
 *
 * Channel resolution: the tool layer may pass a provider-ish name
 * ("feishu"/"webhook"/"email") that does not match any configured
 * channel code. We fall back to the first enabled channel so sends
 * always reach a real destination when at least one is configured.
 */
export class NotificationClient {
  private client: AxiosInstance;
  private channelsCache: NotificationChannel[] | null = null;

  constructor(config: RegistryClientConfig) {
    this.client = createHttpClient(config);
  }

  /**
   * Send a notification (channel resolves to a configured code).
   */
  async send(params: SendNotificationParams): Promise<SendNotificationResponse> {
    if (!params.title || params.title.trim() === '') {
      throw new Error('title is required');
    }
    if (!params.content || params.content.trim() === '') {
      throw new Error('content is required');
    }
    const channel = await this.resolveChannel(params.channel);
    const response = await this.client.post<SendNotificationResponse>(
      '/api/v1/notifications/send',
      {
        channel,
        title: params.title,
        content: params.content,
      }
    );
    return response.data;
  }

  /**
   * List available channels.
   */
  async listChannels(): Promise<{ channels: NotificationChannel[] }> {
    const response = await this.client.get('/api/v1/notifications/channels');
    return response.data;
  }

  /**
   * Resolve the tool-level channel hint to a configured channel code.
   */
  private async resolveChannel(hint?: string): Promise<string> {
    if (this.channelsCache === null) {
      try {
        const data = await this.listChannels();
        this.channelsCache = data.channels || [];
      } catch {
        this.channelsCache = [];
      }
    }
    const channels = this.channelsCache;
    if (hint && channels.some((c) => c.code === hint && c.enabled !== false)) {
      return hint;
    }
    const fallback = channels.find((c) => c.enabled !== false);
    return fallback?.code || hint || 'default';
  }
}

/** Minimal shape of a configured notification channel. */
interface NotificationChannel {
  id: string;
  code: string;
  name?: string;
  provider_id?: string;
  enabled?: boolean;
  [key: string]: any;
}
