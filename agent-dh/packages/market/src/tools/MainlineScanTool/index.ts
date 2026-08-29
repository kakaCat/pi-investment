/**
 * MainlineScanTool - 市场主线扫描工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import type { OsMemoryStore } from '@pi-investment/os-memory';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MainlineScanTool } from './MainlineScanTool';

/**
 * 创建主线扫描工具实例
 */
export function createMainlineScanTool(qv2: QuantsysV2Client, osMemory: OsMemoryStore) {
  const tool = new MainlineScanTool(qv2, osMemory);
  return defineTool(tool.toDSHToolDefinition());
}

export { MainlineScanTool } from './MainlineScanTool';
export type { MainlineScanParams, MainlineScanResult } from './prompt';
