/**
 * 测试工具响应格式的正确性
 * 确保所有工具返回符合框架要求的格式
 */

import { describe, it, expect } from '@jest/globals';
import { handleToolResponse, createErrorResponse } from '../utils/tool-response-handler.js';

describe('Tool Response Format', () => {
  it('should return valid ToolResponse with content array', async () => {
    const response = await handleToolResponse({
      toolName: 'test_tool',
      data: { result: 'test' },
      formatter: (data) => JSON.stringify(data),
    });

    expect(response).toHaveProperty('content');
    expect(Array.isArray(response.content)).toBe(true);
    expect(response.content.length).toBeGreaterThan(0);
    expect(response.content[0]).toHaveProperty('type', 'text');
    expect(response.content[0]).toHaveProperty('text');
  });

  it('should return valid error response with content array', () => {
    const error = new Error('Test error');
    const response = createErrorResponse(error);

    expect(response).toHaveProperty('content');
    expect(Array.isArray(response.content)).toBe(true);
    expect(response.content.length).toBeGreaterThan(0);
    expect(response.content[0]).toHaveProperty('type', 'text');
    expect(response.content[0].text).toContain('Test error');
  });

  it('should have details property (not undefined)', async () => {
    const response = await handleToolResponse({
      toolName: 'test_tool',
      data: { result: 'test' },
    });

    expect(response).toHaveProperty('details');
    expect(response.details).not.toBeUndefined();
  });

  it('should handle error response with details', () => {
    const error = new Error('Test error');
    const response = createErrorResponse(error);

    expect(response).toHaveProperty('details');
    expect(response.details).not.toBeUndefined();
  });
});
