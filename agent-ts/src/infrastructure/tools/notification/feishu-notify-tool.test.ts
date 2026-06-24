/**
 * Feishu Notify Tool Tests
 */
import { describe, it, expect, beforeEach, jest, afterEach } from '@jest/globals';
import { feishuNotifyTool } from './feishu-notify-tool.js';

// Mock the feishu service
jest.mock('../../../services/feishu/feishu-notification-service.js', () => ({
  getFeishuService: jest.fn()
}));

import { getFeishuService } from '../../../services/feishu/feishu-notification-service.js';

describe('feishu-notify-tool', () => {
  let mockFeishuService: any;

  beforeEach(() => {
    // Create mock service
    mockFeishuService = {
      sendText: jest.fn<any>().mockResolvedValue(true),
      sendCard: jest.fn<any>().mockResolvedValue(true),
      sendDailyReport: jest.fn<any>().mockResolvedValue(true),
      sendWeeklyReport: jest.fn<any>().mockResolvedValue(true),
      sendAlert: jest.fn<any>().mockResolvedValue(true),
      sendPremarketReport: jest.fn<any>().mockResolvedValue(true)
    };

    (getFeishuService as any).mockReturnValue(mockFeishuService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Definition', () => {
    it('should have correct name', () => {
      expect(feishuNotifyTool.name).toBe('feishu_notify');
    });

    it('should have label', () => {
      expect(feishuNotifyTool.label).toBe('飞书通知');
    });

    it('should have description', () => {
      expect(feishuNotifyTool.description).toBeDefined();
      expect(feishuNotifyTool.description).toContain('发送飞书通知');
    });

    it('should have parameters schema', () => {
      expect(feishuNotifyTool.parameters).toBeDefined();
    });

    it('should have execute function', () => {
      expect(feishuNotifyTool.execute).toBeDefined();
      expect(typeof feishuNotifyTool.execute).toBe('function');
    });
  });

  describe('Text Message', () => {
    it('should send text message', async () => {
      const params = {
        messageType: 'text',
        content: 'Test message'
      };

      const result = await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect(mockFeishuService.sendText).toHaveBeenCalledWith('Test message', false);
      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');
      expect((result as any).details.success).toBe(true);
    });

    it('should send text with mention', async () => {
      const params = {
        messageType: 'text',
        content: 'Important message',
        mentionUser: true
      };

      await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect(mockFeishuService.sendText).toHaveBeenCalledWith('Important message', true);
    });
  });

  describe('Card Message', () => {
    it('should send card message', async () => {
      const params = {
        messageType: 'card',
        title: 'Test Card',
        content: 'Card content',
        urgency: 'normal'
      };

      const result = await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect(mockFeishuService.sendCard).toHaveBeenCalledWith({
        title: 'Test Card',
        content: 'Card content',
        urgency: 'normal',
        actions: undefined
      });
      expect((result as any).details.success).toBe(true);
    });

    it('should require title for card', async () => {
      const params = {
        messageType: 'card',
        content: 'Card without title'
      };

      const result = await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect((result as any).details.success).toBe(false);
      expect((result as any).details.error).toContain('title');
    });
  });

  describe('Alert Message', () => {
    it('should send alert', async () => {
      const params = {
        messageType: 'alert',
        title: 'Risk Alert',
        content: 'Market volatility high',
        urgency: 'critical'
      };

      const result = await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect(mockFeishuService.sendAlert).toHaveBeenCalledWith({
        title: 'Risk Alert',
        content: 'Market volatility high',
        urgency: 'critical',
        actions: undefined,
        mentionUser: false
      });
      expect((result as any).details.success).toBe(true);
    });
  });

  describe('Report Messages', () => {
    it('should send daily report', async () => {
      const params = {
        messageType: 'daily_report',
        content: 'Daily content',
        data: { portfolio: 'summary', pnl: 1000 }
      };

      const result = await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect(mockFeishuService.sendDailyReport).toHaveBeenCalledWith({
        portfolio: 'summary',
        pnl: 1000
      });
      expect((result as any).details.success).toBe(true);
    });

    it('should require data for daily report', async () => {
      const params = {
        messageType: 'daily_report',
        content: 'Content'
      };

      const result = await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect((result as any).details.success).toBe(false);
      expect((result as any).details.error).toContain('data');
    });
  });

  describe('Service Unavailable', () => {
    it('should handle missing service gracefully', async () => {
      (getFeishuService as any).mockReturnValue(null);

      const params = {
        messageType: 'text',
        content: 'Test'
      };

      const result = await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect((result as any).details.success).toBe(false);
      expect((result as any).details.message).toContain('未配置');
    });
  });

  describe('Error Handling', () => {
    it('should handle service errors', async () => {
      mockFeishuService.sendText.mockRejectedValue(new Error('Network error'));

      const params = {
        messageType: 'text',
        content: 'Test'
      };

      const result = await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect((result as any).details.success).toBe(false);
      expect((result as any).details.error).toContain('Network error');
    });

    it('should handle failed send', async () => {
      mockFeishuService.sendText.mockResolvedValue(false);

      const params = {
        messageType: 'text',
        content: 'Test'
      };

      const result = await (feishuNotifyTool.execute as any)('test-call-id', params);

      expect((result as any).details.success).toBe(false);
      expect((result as any).details.message).toContain('发送失败');
    });
  });
});
