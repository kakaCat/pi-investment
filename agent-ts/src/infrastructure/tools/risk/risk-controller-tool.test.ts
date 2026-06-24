/**
 * Risk Controller Tool - 测试文件
 */

import { describe, it, expect, vi } from 'vitest';
import { riskControllerTool } from './risk-controller-tool.js';
import * as quantV2Client from '../../adapters/quant/quant-v2-client.js';

vi.mock('../../adapters/quant/quant-v2-client.js');

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

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

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

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

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
