/**
 * RiskControllerTool - 风险控制工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { RiskControllerTool } from './RiskControllerTool';

/**
 * 创建风险控制工具实例
 */
interface OsMemoryStore {
  searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<{ items: any[] }>;
}

/**
 * 2026-09-13（w-c8cae280）：新增 memoryClient —— position_size 需要读 regime 记录做"余量钳制"。
 */
export function createRiskControllerTool(qv2: QuantsysV2Client, memoryClient?: OsMemoryStore) {
  const tool = new RiskControllerTool(qv2, memoryClient);
  return defineTool(tool.toDSHToolDefinition());
}

export { RiskControllerTool } from './RiskControllerTool';
export type { RiskControllerParams, RiskControllerResult } from './prompt';
