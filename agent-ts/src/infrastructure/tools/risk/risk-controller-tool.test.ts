/**
 * Risk Controller Tool - 测试文件
 */

import { describe, it, expect, jest } from '@jest/globals';

const mockRunQuantV2 = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule('../../adapters/quant/quant-v2-client.js', () => ({
  runQuantV2: mockRunQuantV2,
}));

const { riskControllerTool } = await import('./risk-controller-tool.js');

describe('risk_controller tool', () => {
  it('should have correct metadata', () => {
    expect(riskControllerTool.name).toBe('risk_controller');
    expect(riskControllerTool.label).toBe('风险控制');
    expect(riskControllerTool.description).toContain('风险控制工具');
  });

  it('should execute trade_check command', async () => {
    const mockResult = {
      ok: true,
      command: 'risk.trade-check',
      data: { passed: true, risk_score: 0.3 },
      error: null,
    };

    mockRunQuantV2.mockResolvedValue(mockResult);

    const result = await riskControllerTool.execute('test', {
      command: 'trade_check',
      params: {
        symbol: '600519',
        action: 'buy',
        price: 1800,
        shares: 100
      }
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('命令执行成功');
      expect((content as any).text).toContain('passed');
    }
  });

  it('should execute position_size command', async () => {
    const mockResult = {
      ok: true,
      command: 'risk.position-size',
      data: { suggested_shares: 200, position_pct: 0.15 },
      error: null,
    };

    mockRunQuantV2.mockResolvedValue(mockResult);

    const result = await riskControllerTool.execute('test', {
      command: 'position_size',
      params: {
        symbol: '600519',
        price: 1800,
        signal_strength: 0.8
      }
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('命令执行成功');
    }
  });

  it('should reject invalid command', async () => {
    const result = await riskControllerTool.execute('test', {
      command: 'invalid_command',
      params: {}
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('未知命令');
    }
  });

  it('should validate required params', async () => {
    const result = await riskControllerTool.execute('test', {
      command: 'trade_check',
      params: { symbol: '600519' } // missing required params
    }, undefined, undefined, {} as any);

    const content = result.content[0];
    if (content.type === 'text') {
      expect((content as any).text).toContain('参数');
    }
  });
});
