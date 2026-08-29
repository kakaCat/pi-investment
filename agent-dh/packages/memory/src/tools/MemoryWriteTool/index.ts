/**
 * MemoryWriteTool - 记忆写入工具导出
 */

import type { OsMemoryStore } from '@pi-investment/os-memory';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MemoryWriteTool } from './MemoryWriteTool';

/**
 * 创建记忆写入工具实例
 */
export function createMemoryWriteTool(osMemory: OsMemoryStore) {
  const tool = new MemoryWriteTool(osMemory);
  return defineTool(tool.toDSHToolDefinition());
}

export { MemoryWriteTool } from './MemoryWriteTool';
export { memoryWritePrompt } from './prompt';
export type { MemoryWriteParams, MemoryWriteResult } from './prompt';
