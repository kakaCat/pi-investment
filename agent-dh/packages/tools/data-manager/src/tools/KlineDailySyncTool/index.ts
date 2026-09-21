import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { KlineDailySyncTool } from './KlineDailySyncTool';

/**
 * 创建K线每日同步工具实例
 */
export function createKlineDailySyncTool(qv2: QuantsysV2Client) {
  const tool = new KlineDailySyncTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { KlineDailySyncTool } from './KlineDailySyncTool';
export { klineDailySyncPrompt } from './prompt';
export type { KlineDailySyncParams, KlineDailySyncResult } from './prompt';
