/**
 * RegimePositionLimitTool - 市场状态仓位限制工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import type { OsMemoryStore } from '@pi-investment/os-memory';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { RegimePositionLimitTool } from './RegimePositionLimitTool';

/**
 * 创建市场状态仓位限制工具实例
 */
export function createRegimePositionLimitTool(qv2: QuantsysV2Client, osMemory: OsMemoryStore) {
  const tool = new RegimePositionLimitTool(qv2, osMemory);
  return defineTool(tool.toDSHToolDefinition());
}

export { RegimePositionLimitTool } from './RegimePositionLimitTool';
export type { RegimePositionLimitParams, RegimePositionLimitResult } from './prompt';
