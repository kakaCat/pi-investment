/**
 * MemorySearchTool - 记忆搜索工具导出
 */

import type { MemoryClient } from '@pi-investment/agent-os-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MemorySearchTool } from './MemorySearchTool';

/**
 * 创建记忆搜索工具实例
 */
export function createMemorySearchTool(memoryClient: MemoryClient) {
  const tool = new MemorySearchTool(memoryClient);
  return defineTool(tool.toDSHToolDefinition());
}

export { MemorySearchTool } from './MemorySearchTool';
export { memorySearchPrompt } from './prompt';
export type { MemorySearchParams, MemorySearchResult, MemoryItem } from './prompt';
