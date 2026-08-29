/**
 * MemoryWriteTool - 记忆写入工具导出
 */

import type { MemoryClient } from '@pi-investment/agent-os-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MemoryWriteTool } from './MemoryWriteTool';

/**
 * 创建记忆写入工具实例
 */
export function createMemoryWriteTool(memoryClient: MemoryClient) {
  const tool = new MemoryWriteTool(memoryClient);
  return defineTool(tool.toDSHToolDefinition());
}

export { MemoryWriteTool } from './MemoryWriteTool';
export { memoryWritePrompt } from './prompt';
export type { MemoryWriteParams, MemoryWriteResult } from './prompt';
