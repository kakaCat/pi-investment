import { FeishuNotificationService } from './feishu-service.js';

export class NotificationFactory {
  static createFeishuService(): FeishuNotificationService | null {
    const webhook = process.env.FEISHU_WEBHOOK;

    if (!webhook) {
      console.warn('未配置 FEISHU_WEBHOOK，通知功能将被禁用');
      return null;
    }

    return new FeishuNotificationService(webhook);
  }

  static getFeishuService(): FeishuNotificationService {
    const service = this.createFeishuService();
    if (!service) {
      throw new Error('Feishu 通知服务未配置，请设置 FEISHU_WEBHOOK 环境变量');
    }
    return service;
  }
}
