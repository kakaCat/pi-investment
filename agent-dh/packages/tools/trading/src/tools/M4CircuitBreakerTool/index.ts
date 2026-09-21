/**
 * M4CircuitBreakerTool - 导出和 DSH 适配器
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { M4CircuitBreakerTool } from './M4CircuitBreakerTool';

export { M4CircuitBreakerTool } from './M4CircuitBreakerTool';
export { circuitBreakerPrompt } from './prompt';
export type { CircuitBreakerCheckParams, CircuitBreakerCheckResult } from './prompt';

/**
 * 创建 DSH 工具
 */
export function createM4CircuitBreakerTool(qv2: QuantsysV2Client, osMemory: any) {
  const tool = new M4CircuitBreakerTool(qv2, osMemory);

  // 使用 BaseTool 的 toDSHToolDefinition() 方法转换为 DSH 格式
  return defineTool(tool.toDSHToolDefinition() as any);
}
