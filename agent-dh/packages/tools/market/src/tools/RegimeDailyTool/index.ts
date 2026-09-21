/**
 * RegimeDailyTool - 市场 Regime 每日落库工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { RegimeDailyTool } from './RegimeDailyTool';

export { regimeDailyPrompt } from './prompt';
export type { RegimeDailyParams, RegimeDailyResult } from './prompt';
export { RegimeDailyTool } from './RegimeDailyTool';

interface OsMemoryStore {
  searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<{ items: any[] }>;
  createMemory(entry: { kind: string; scope: string; title: string; content: string; payload?: any; status?: string; confidence?: number; source?: string; provenance?: any }): Promise<{ id: string }>;
}

export function createRegimeDailyTool(qv2: QuantsysV2Client, memoryClient: OsMemoryStore) {
  const tool = new RegimeDailyTool(qv2, memoryClient);
  return defineTool(tool.toDSHToolDefinition() as any);
}
