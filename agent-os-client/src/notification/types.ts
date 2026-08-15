/**
 * Notification channel
 */
export interface NotificationChannel {
  id: string;
  name: string;
  type: 'feishu' | 'wechat' | 'email' | 'webhook';
  config: any;
  enabled: boolean;
  created_at: string;
}

/**
 * Notification send request
 */
export interface NotificationSendRequest {
  channel?: string;
  title: string;
  content: string;
  urgency?: 'low' | 'normal' | 'high' | 'critical';
  recipients?: string[];
  metadata?: any;
}

/**
 * Notification record
 */
export interface Notification {
  id: string;
  channel: string;
  title: string;
  content: string;
  urgency: 'low' | 'normal' | 'high' | 'critical';
  status: 'pending' | 'sent' | 'failed';
  sent_at?: string;
  error?: string;
  metadata?: any;
  created_at: string;
}

/**
 * Notification list filters
 */
export interface NotificationListFilters {
  channel?: string;
  status?: 'pending' | 'sent' | 'failed';
  urgency?: 'low' | 'normal' | 'high' | 'critical';
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}
