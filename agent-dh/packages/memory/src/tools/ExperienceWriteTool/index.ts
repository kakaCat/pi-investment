/**
 * ExperienceWriteTool - 经验写入工具导出
 */

import type { MemoryClient } from '@pi-investment/agent-os-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { ExperienceWriteTool } from './ExperienceWriteTool';

/**
 * 创建经验写入工具实例
 */
export function createExperienceWriteTool(memoryClient: MemoryClient) {
  const tool = new ExperienceWriteTool(memoryClient);
  return defineTool(tool.toDSHToolDefinition());
}

export { ExperienceWriteTool } from './ExperienceWriteTool';
export { experienceWritePrompt } from './prompt';
export type { ExperienceWriteParams, ExperienceWriteResult } from './prompt';
