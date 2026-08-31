/**
 * DailyDistillTool - 每日蒸馏编排工具
 */

import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import type { OsMemoryStore } from '../../index';
import { DailyDistillTool } from './DailyDistillTool';

export { dailyDistillPrompt } from './prompt';
export type { DailyDistillParams, DailyDistillResult } from './prompt';
export { DailyDistillTool } from './DailyDistillTool';

/**
 * 创建 DSH 工具
 */
export function createDailyDistillTool(
  ctx: Context,
  osMemory: OsMemoryStore
) {
  const tool = new DailyDistillTool(ctx, osMemory);
  return defineTool(tool.toDSHToolDefinition() as any);
}
