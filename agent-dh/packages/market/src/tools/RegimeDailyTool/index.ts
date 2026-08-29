/**
 * RegimeDailyTool - 市场 Regime 每日落库工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import type { OsMemoryStore } from '@pi-investment/os-memory';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { RegimeDailyTool } from './RegimeDailyTool';

export { regimeDailyPrompt } from './prompt';
export type { RegimeDailyParams, RegimeDailyResult } from './prompt';
export { RegimeDailyTool } from './RegimeDailyTool';

/**
 * 创建 DSH 工具
 */
export function createRegimeDailyTool(qv2: QuantsysV2Client, osMemory: OsMemoryStore) {
  const tool = new RegimeDailyTool(qv2, osMemory);
  return defineTool(tool.toDSHToolDefinition() as any);
}
