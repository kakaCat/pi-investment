/**
 * Data Manager Tool - 测试文件
 */

import { describe, it, expect, vi } from 'vitest';
import { dataManagerTool } from './data-manager-tool.js';
import * as quantV2Client from '../../adapters/quant/quant-v2-client.js';

vi.mock('../../adapters/quant/quant-v2-client.js');

describe('data_manager tool', () => {
  it('should have correct metadata', () => {
    expect(dataManagerTool.name).toBe('data_manager');
    expect(dataManagerTool.label).toBe('数据管理');
    expect(dataManagerTool.description).toContain('量化数据管理工具');
  });

  it('should execute status command', async () => {
    const mockResult = {
      ok: true,
      command: 'data.status',
      data: { total_stocks: 5000, last_update: '2024-01-01' },
      error: null,
    };

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await dataManagerTool.execute('test', {
      command: 'status',
      params: {}
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('命令执行成功');
      expect(content.text).toContain('total_stocks');
    }
  });

  it('should execute update command', async () => {
    const mockResult = {
      ok: true,
      command: 'data.update',
      data: { updated: 100, success: true },
      error: null,
    };

    vi.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue(mockResult);

    const result = await dataManagerTool.execute('test', {
      command: 'update',
      params: { source: 'all' }
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('命令执行成功');
    }
  });

  it('should reject invalid command', async () => {
    const result = await dataManagerTool.execute('test', {
      command: 'invalid_command',
      params: {}
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('未知命令');
    }
  });

  it('should validate required params', async () => {
    const result = await dataManagerTool.execute('test', {
      command: 'update',
      params: {} // missing required 'source'
    });

    const content = result.content[0];
    if (content.type === 'text') {
      expect(content.text).toContain('参数');
    }
  });
});
