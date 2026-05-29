import { describe, it, expect } from '@jest/globals';
import { test_toolTool } from './test_tool-tool.js';

describe('test_toolTool', () => {
  it('should execute successfully with valid params', async () => {
    const result = await (test_toolTool.execute as any)('test-id', {
      message: '结果文本',
    });

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.content[0]).toEqual({ type: 'text', text: '结果文本' });
    expect(result.details.success).toBe(true);
  });

  it('should handle invalid params gracefully', async () => {
    const result = await (test_toolTool.execute as any)('test-id', {});

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.success).toBe(true);
  });
});