/**
 * MainlineScanTool - 市场主线扫描工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MainlineScanTool } from './MainlineScanTool';

export { MainlineScanTool } from './MainlineScanTool';
export type { MainlineScanParams, MainlineScanResult } from './prompt';

interface OsMemoryStore {
  searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<{ items: any[] }>;
  createMemory(entry: { kind: string; scope: string; title: string; content: string; payload?: any; status?: string; confidence?: number; source?: string; provenance?: any }): Promise<{ id: string }>;
}

export function createMainlineScanTool(qv2: QuantsysV2Client, memoryClient: OsMemoryStore) {
  const tool = new MainlineScanTool(qv2, memoryClient);
  return defineTool(tool.toDSHToolDefinition());
}
