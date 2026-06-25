import { describe, it, expect } from '@jest/globals';
import { test_toolTool } from './test_tool-tool.js';

describe('test_toolTool', () => {
  it('should execute successfully with valid params', async () => {
    const result = await (test_toolTool.execute as any)('test-id', {
      input: '测试参数',
    });

    expect(result.content).toBeDefined();
    expect(result.content[0]).toEqual({
      type: 'text',
      text: '结果文本: 测试参数',
    });
    expect(result.details).toBeDefined();
    expect(result.details.success).toBe(true);
    expect(result.details.toolCallId).toBe('test-id');
    expect(result.details.input).toBe('测试参数');
  });

  it('should handle invalid params gracefully', async () => {
    const result = await (test_toolTool.execute as any)('test-id', {});

    expect(result.content).toBeDefined();
    expect(result.content[0]).toEqual({
      type: 'text',
      text: '结果文本',
    });
    expect(result.details).toBeDefined();
    expect(result.details.success).toBe(true);
  });
});