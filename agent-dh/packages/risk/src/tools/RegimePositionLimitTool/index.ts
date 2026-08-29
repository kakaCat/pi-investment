/**
 * RegimePositionLimitTool - 市场状态仓位限制工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { RegimePositionLimitTool } from './RegimePositionLimitTool';

export { RegimePositionLimitTool } from './RegimePositionLimitTool';
export type { RegimePositionLimitParams, RegimePositionLimitResult } from './prompt';

interface OsMemoryStore {
  searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<{ items: any[] }>;
  createMemory(entry: { kind: string; scope: string; title: string; content: string; payload?: any; status?: string; confidence?: number; source?: string; provenance?: any }): Promise<{ id: string }>;
}

export function createRegimePositionLimitTool(qv2: QuantsysV2Client, memoryClient: OsMemoryStore) {
  const tool = new RegimePositionLimitTool(qv2, memoryClient);
  return defineTool(tool.toDSHToolDefinition());
}
