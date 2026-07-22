/**
 * Monitor Alert Tool Tests - Business Logic Coverage
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { monitorAlertTool } from './alert-tool.js';

// Helper to extract text from result
const getText = (result: any): string => {
  const content = result.content[0];
  return content.type === 'text' ? (content as any).text : '';
};

// Mock notification tools
jest.mock('../shared/notification-tools.js', () => ({
  sendNotificationTool: {
    execute: jest.fn(async () => ({
      content: [{ type: 'text', text: '通知已发送' }],
      details: undefined
    }))
  },
  sendTradeSignalTool: {
    execute: jest.fn(async () => ({
      content: [{ type: 'text', text: '交易信号已发送' }],
      details: undefined
    }))
  },
  sendMarketBriefTool: {
    execute: jest.fn(async () => ({
      content: [{ type: 'text', text: '市场简报已发送' }],
      details: undefined
    }))
  },
  sendRiskWarningTool: {
    execute: jest.fn(async () => ({
      content: [{ type: 'text', text: '风险警告已发送' }],
      details: undefined
    }))
  }
}));

describe('monitorAlertTool - Tool Definition', () => {
  it('should have correct tool name', () => {
    expect(monitorAlertTool.name).toBe('monitor_alert');
  });

  it('should have correct label', () => {
    expect(monitorAlertTool.label).toBe('监控告警');
  });

  it('should have description mentioning all notification types', () => {
    expect(monitorAlertTool.description).toContain('general');
    expect(monitorAlertTool.description).toContain('trade_signal');
    expect(monitorAlertTool.description).toContain('market_brief');
    expect(monitorAlertTool.description).toContain('risk_warning');
  });

  it('should have parameters object', () => {
    expect(monitorAlertTool.parameters).toBeDefined();
    expect(typeof monitorAlertTool.parameters).toBe('object');
  });

  it('should have execute function', () => {
    expect(monitorAlertTool.execute).toBeDefined();
    expect(typeof monitorAlertTool.execute).toBe('function');
  });

  it('should have type parameter with all notification types', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties).toBeDefined();
    expect(params.properties.type).toBeDefined();
  });

  it('should support general notification parameters', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties.message).toBeDefined();
    expect(params.properties.title).toBeDefined();
  });

  it('should support trade signal parameters', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties.action).toBeDefined();
    expect(params.properties.symbol).toBeDefined();
    expect(params.properties.confidence).toBeDefined();
  });

  it('should support market brief parameters', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties.summary).toBeDefined();
    expect(params.properties.indices).toBeDefined();
  });

  it('should support risk warning parameters', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties.warning).toBeDefined();
    expect(params.properties.severity).toBeDefined();
  });
});

describe('monitorAlertTool - Business Logic', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('type: general', () => {
    it('should send general notification with message', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'general',
        message: '测试通知消息'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('通知已发送');
    });

    it('should send general notification with title and message', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'general',
        title: '重要通知',
        message: '测试通知消息'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('通知已发送');
    });

    it('should reject general notification without message', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'general'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('message');
    });
  });

  describe('type: trade_signal', () => {
    it('should send trade signal with all required parameters', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'trade_signal',
        action: 'buy',
        symbol: '600519',
        name: '贵州茅台',
        price: 1800,
        reason: '技术面突破',
        confidence: 0.85
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('交易信号已发送');
    });

    it('should send trade signal with optional position_pct', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'trade_signal',
        action: 'sell',
        symbol: '600519',
        name: '贵州茅台',
        price: 1800,
        reason: '止盈',
        confidence: 0.75,
        position_pct: 50
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('交易信号已发送');
    });

    it('should reject trade signal without action', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'trade_signal',
        symbol: '600519',
        name: '贵州茅台',
        price: 1800,
        reason: '技术面突破',
        confidence: 0.85
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('action');
    });

    it('should reject trade signal without symbol', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'trade_signal',
        action: 'buy',
        name: '贵州茅台',
        price: 1800,
        reason: '技术面突破',
        confidence: 0.85
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('symbol');
    });

    it('should reject trade signal without name', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'trade_signal',
        action: 'buy',
        symbol: '600519',
        price: 1800,
        reason: '技术面突破',
        confidence: 0.85
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('name');
    });

    it('should reject trade signal without price', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'trade_signal',
        action: 'buy',
        symbol: '600519',
        name: '贵州茅台',
        reason: '技术面突破',
        confidence: 0.85
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('price');
    });

    it('should reject trade signal without reason', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'trade_signal',
        action: 'buy',
        symbol: '600519',
        name: '贵州茅台',
        price: 1800,
        confidence: 0.85
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('reason');
    });

    it('should reject trade signal without confidence', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'trade_signal',
        action: 'buy',
        symbol: '600519',
        name: '贵州茅台',
        price: 1800,
        reason: '技术面突破'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('confidence');
    });
  });

  describe('type: market_brief', () => {
    it('should send market brief with all required parameters', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'market_brief',
        summary: '今日市场震荡上行',
        indices: {
          '上证指数': { value: 3200, change: 1.5 },
          '深证成指': { value: 11000, change: 2.0 }
        }
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('市场简报已发送');
    });

    it('should send market brief with optional highlights', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'market_brief',
        summary: '今日市场震荡上行',
        indices: {
          '上证指数': { value: 3200, change: 1.5 }
        },
        highlights: ['科技股领涨', '成交量放大']
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('市场简报已发送');
    });

    it('should reject market brief without summary', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'market_brief',
        indices: {
          '上证指数': { value: 3200, change: 1.5 }
        }
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('summary');
    });

    it('should reject market brief without indices', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'market_brief',
        summary: '今日市场震荡上行'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('indices');
    });
  });

  describe('type: risk_warning', () => {
    it('should send risk warning with all required parameters', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'risk_warning',
        warning: '持仓集中度过高',
        severity: 'high'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('风险警告已发送');
    });

    it('should send risk warning with optional details and suggestion', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'risk_warning',
        warning: '持仓集中度过高',
        severity: 'medium',
        details: '单一股票占比超过30%',
        suggestion: '建议分散投资'
      }, undefined, undefined, {} as any);

      const text = getText(result);
      expect(text).toContain('风险警告已发送');
    });

    it('should reject risk warning without warning', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'risk_warning',
        severity: 'high'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('warning');
    });

    it('should reject risk warning without severity', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'risk_warning',
        warning: '持仓集中度过高'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('severity');
    });

    it('should support all severity levels', async () => {
      const severities = ['low', 'medium', 'high'];

      for (const severity of severities) {
        const result = await monitorAlertTool.execute('test-id', {
          type: 'risk_warning',
          warning: '测试警告',
          severity
        }, undefined, undefined, {} as any);

        const text = getText(result);
        expect(text).toContain('风险警告已发送');
      }
    });
  });

  describe('error handling', () => {
    it('should handle unknown notification type', async () => {
      const result = await monitorAlertTool.execute('test-id', {
        type: 'unknown_type'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('未知通知类型');
      expect(response.valid_types).toContain('general');
      expect(response.valid_types).toContain('trade_signal');
      expect(response.valid_types).toContain('market_brief');
      expect(response.valid_types).toContain('risk_warning');
    });

    it('should handle service errors gracefully', async () => {
// @ts-ignore - Module stub needed
      const { sendNotificationTool } = await import('../shared/notification-tools.js');
      (sendNotificationTool.execute as any).mockRejectedValueOnce(new Error('Network error'));

      const result = await monitorAlertTool.execute('test-id', {
        type: 'general',
        message: '测试消息'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.error).toContain('Network error');
    });
  });
});
