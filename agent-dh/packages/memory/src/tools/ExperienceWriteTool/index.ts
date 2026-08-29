/**
 * ExperienceWriteTool - 经验写入工具导出
 */

import type { OsMemoryStore } from '@pi-investment/os-memory';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { ExperienceWriteTool } from './ExperienceWriteTool';

/**
 * 创建经验写入工具实例
 */
export function createExperienceWriteTool(osMemory: OsMemoryStore) {
  const tool = new ExperienceWriteTool(osMemory);
  return defineTool(tool.toDSHToolDefinition());
}

export { ExperienceWriteTool } from './ExperienceWriteTool';
export { experienceWritePrompt } from './prompt';
export type { ExperienceWriteParams, ExperienceWriteResult } from './prompt';
