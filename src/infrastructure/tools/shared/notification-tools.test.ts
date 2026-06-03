/**
 * Notification Tools Tests
 */
import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { NotificationService } from '../services/notification/notification-service.js';
import {
  initNotificationService,
  getNotificationService,
  sendNotificationTool,
  sendTradeSignalTool,
  sendMarketBriefTool,
  sendRiskWarningTool,
  notificationTools
} from './notification-tools.js';

describe('Notification Tools', () => {
  let service: NotificationService;
  let sendSpy: jest.SpiedFunction<typeof service.send>;
  let sendCardSpy: jest.SpiedFunction<typeof service.sendCard>;

  beforeEach(() => {
    // Initialize service
    service = initNotificationService();

    // Spy on methods
    sendSpy = jest.spyOn(service, 'send').mockResolvedValue(undefined);
    sendCardSpy = jest.spyOn(service, 'sendCard').mockResolvedValue(undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Service Initialization', () => {
    it('should initialize notification service', () => {
      const service = initNotificationService();
      expect(service).toBeDefined();
      expect(service).toBeInstanceOf(NotificationService);
    });

    it('should return singleton instance', () => {
      const service1 = initNotificationService();
      const service2 = getNotificationService();
      expect(service1).toBe(service2);
    });
  });

  describe('send_notification tool', () => {
    it('should send generic notification', async () => {
      const params = {
        message: 'Test notification',
        title: 'Test Title'
      };

      const result = await (sendNotificationTool.execute as any)('test-call-id', params);

      expect(sendSpy).toHaveBeenCalledWith('Test notification');
      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.success).toBe(true);
      expect(response.message).toContain('通知已发送');
    });

    it('should handle notification without title', async () => {
      const params = {
        message: 'Simple message'
      };

      const result = await (sendNotificationTool.execute as any)('test-call-id', params);

      expect(sendSpy).toHaveBeenCalledWith('Simple message');
      expect(result.details).toBeUndefined();
    });

    it('should handle service errors gracefully', async () => {
      sendSpy.mockRejectedValue(new Error('Network error'));

      const params = {
        message: 'Test message'
      };

      const result = await (sendNotificationTool.execute as any)('test-call-id', params);

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.success).toBe(false);
      expect(response.error).toContain('Network error');
    });
  });

  describe('send_trade_signal tool', () => {
    it('should send buy signal', async () => {
      const params = {
        action: 'buy',
        symbol: '600519',
        name: '贵州茅台',
        price: 1800.50,
        reason: '技术面突破，基本面良好',
        confidence: 0.85,
        position_pct: 15
      };

      const result = await (sendTradeSignalTool.execute as any)('test-call-id', params);

      expect(sendCardSpy).toHaveBeenCalledTimes(1);
      const callArgs = sendCardSpy.mock.calls[0][0];

      expect(callArgs.type).toBe('card');
      expect(callArgs.title).toContain('买入信号');
      expect(callArgs.content).toContain('600519');
      expect(callArgs.content).toContain('贵州茅台');
      expect(callArgs.content).toContain('1800.50');
      expect(callArgs.metadata).toEqual(params);

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.success).toBe(true);
    });

    it('should send sell signal', async () => {
      const params = {
        action: 'sell',
        symbol: '000001',
        name: '平安银行',
        price: 12.50,
        reason: '技术面走弱',
        confidence: 0.75
      };

      const result = await (sendTradeSignalTool.execute as any)('test-call-id', params);

      expect(sendCardSpy).toHaveBeenCalledTimes(1);
      const callArgs = sendCardSpy.mock.calls[0][0];

      expect(callArgs.title).toContain('卖出信号');
      expect(callArgs.content).toContain('000001');
    });

    it('should format confidence as percentage', async () => {
      const params = {
        action: 'buy',
        symbol: '600519',
        name: '贵州茅台',
        price: 1800.50,
        reason: '测试',
        confidence: 0.856
      };

      await (sendTradeSignalTool.execute as any)('test-call-id', params);

      const callArgs = sendCardSpy.mock.calls[0][0];
      expect(callArgs.content).toContain('85.6%');
    });
  });

  describe('send_market_brief tool', () => {
    it('should send market summary', async () => {
      const params = {
        summary: '今日市场震荡上行',
        indices: {
          '上证指数': { value: 3200, change: 1.5 },
          '深证成指': { value: 11000, change: 2.1 }
        },
        highlights: ['科技股领涨', '成交量放大']
      };

      const result = await (sendMarketBriefTool.execute as any)('test-call-id', params);

      expect(sendCardSpy).toHaveBeenCalledTimes(1);
      const callArgs = sendCardSpy.mock.calls[0][0];

      expect(callArgs.type).toBe('card');
      expect(callArgs.title).toContain('市场简报');
      expect(callArgs.content).toContain('今日市场震荡上行');
      expect(callArgs.content).toContain('上证指数');
      expect(callArgs.content).toContain('+1.5%');
      expect(callArgs.content).toContain('科技股领涨');

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.success).toBe(true);
    });

    it('should handle negative changes', async () => {
      const params = {
        summary: '市场调整',
        indices: {
          '上证指数': { value: 3100, change: -1.2 }
        }
      };

      await (sendMarketBriefTool.execute as any)('test-call-id', params);

      const callArgs = sendCardSpy.mock.calls[0][0];
      expect(callArgs.content).toContain('-1.2%');
    });

    it('should handle optional highlights', async () => {
      const params = {
        summary: '市场平稳',
        indices: {
          '上证指数': { value: 3200, change: 0.1 }
        }
      };

      const result = await (sendMarketBriefTool.execute as any)('test-call-id', params);

      expect(sendCardSpy).toHaveBeenCalledTimes(1);
      const response = JSON.parse((result.content[0] as any).text);
      expect(response.success).toBe(true);
    });
  });

  describe('send_risk_warning tool', () => {
    it('should send high severity warning', async () => {
      const params = {
        warning: '持仓集中度过高',
        severity: 'high',
        details: '前三大持仓占比超过60%',
        suggestion: '建议分散投资'
      };

      const result = await (sendRiskWarningTool.execute as any)('test-call-id', params);

      expect(sendCardSpy).toHaveBeenCalledTimes(1);
      const callArgs = sendCardSpy.mock.calls[0][0];

      expect(callArgs.type).toBe('card');
      expect(callArgs.title).toContain('⚠️ 风险警告');
      expect(callArgs.content).toContain('持仓集中度过高');
      expect(callArgs.content).toContain('**严重程度**: 高');
      expect(callArgs.content).toContain('前三大持仓占比超过60%');
      expect(callArgs.content).toContain('建议分散投资');

      const response = JSON.parse((result.content[0] as any).text);
      expect(response.success).toBe(true);
    });

    it('should send medium severity warning', async () => {
      const params = {
        warning: '市场波动加大',
        severity: 'medium',
        details: 'VIX指数上升'
      };

      await (sendRiskWarningTool.execute as any)('test-call-id', params);

      const callArgs = sendCardSpy.mock.calls[0][0];
      expect(callArgs.content).toContain('**严重程度**: 中');
    });

    it('should send low severity warning', async () => {
      const params = {
        warning: '关注市场动态',
        severity: 'low'
      };

      await (sendRiskWarningTool.execute as any)('test-call-id', params);

      const callArgs = sendCardSpy.mock.calls[0][0];
      expect(callArgs.content).toContain('**严重程度**: 低');
    });

    it('should handle optional fields', async () => {
      const params = {
        warning: '简单警告',
        severity: 'low'
      };

      const result = await (sendRiskWarningTool.execute as any)('test-call-id', params);

      expect(sendCardSpy).toHaveBeenCalledTimes(1);
      const response = JSON.parse((result.content[0] as any).text);
      expect(response.success).toBe(true);
    });
  });

  describe('notificationTools array', () => {
    it('should export all 4 tools', () => {
      expect(notificationTools).toHaveLength(4);
      expect(notificationTools).toContain(sendNotificationTool);
      expect(notificationTools).toContain(sendTradeSignalTool);
      expect(notificationTools).toContain(sendMarketBriefTool);
      expect(notificationTools).toContain(sendRiskWarningTool);
    });

    it('should have correct tool names', () => {
      const toolNames = notificationTools.map(tool => tool.name);
      expect(toolNames).toContain('send_notification');
      expect(toolNames).toContain('send_trade_signal');
      expect(toolNames).toContain('send_market_brief');
      expect(toolNames).toContain('send_risk_warning');
    });
  });
});
