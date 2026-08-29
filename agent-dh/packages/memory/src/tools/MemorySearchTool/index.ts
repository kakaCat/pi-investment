/**
 * MemorySearchTool - 记忆搜索工具导出
 */

import type { OsMemoryStore } from '@pi-investment/os-memory';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MemorySearchTool } from './MemorySearchTool';

/**
 * 创建记忆搜索工具实例
 */
export function createMemorySearchTool(osMemory: OsMemoryStore) {
  const tool = new MemorySearchTool(osMemory);
  return defineTool(tool.toDSHToolDefinition());
}

export { MemorySearchTool } from './MemorySearchTool';
export { memorySearchPrompt } from './prompt';
export type { MemorySearchParams, MemorySearchResult, MemoryItem } from './prompt';
