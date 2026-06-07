/**
 * Factor Academic Tool - 测试文件
 */

import { describe, it, expect, vi } from 'vitest';
import { factorAcademicTool } from './factor-academic-tool.js';
import * as quantV2Client from '../../adapters/quant/quant-v2-client.js';

vi.mock('../../adapters/quant/quant-v2-client.js');

describe('factor_academic tool', () => {
  it('should have correct metadata', () => {
    expect(factorAcademicTool.name).toBe('factor_academic');
    expect(factorAcademicTool.label).toBe('学术因子');
    expect(factorAcademicTool.description).toContain('学术级多因子');
  });

  it('should execute list command', async () => {
    const mockResult = {
      ok: true,
      command: 'factor.list',
      data: { factors: ['rsi', 'macd', 'roe'] },
      error: null,
    };

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await factorAcademicTool.execute('test', {
      command: 'list',
      params: { symbol: '600519' }
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('命令执行成功');
    }
  });

  it('should execute fama_french_5 command', async () => {
    const mockResult = {
      ok: true,
      command: 'factor.fama-french-5',
      data: {
        factors: {
          market: 0.05,
          size: 0.02,
          value: 0.03,
          profitability: 0.01,
          investment: -0.01
        }
      },
      error: null,
    };

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await factorAcademicTool.execute('test', {
      command: 'fama_french_5',
      params: {
        symbols: ['600000', '000001'],
        start_date: '2023-01-01'
      }
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('命令执行成功');
    }
  });

  it('should reject invalid command', async () => {
    const result = await factorAcademicTool.execute('test', {
      command: 'invalid_command',
      params: {}
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('未知命令');
    }
  });

  it('should validate required params', async () => {
    const result = await factorAcademicTool.execute('test', {
      command: 'fama_french_5',
      params: {} // missing required 'symbols'
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('参数');
    }
  });
});
