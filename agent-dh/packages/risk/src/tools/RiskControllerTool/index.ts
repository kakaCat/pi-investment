/**
 * RiskControllerTool - 风险控制工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { RiskControllerTool } from './RiskControllerTool';

/**
 * 创建风险控制工具实例
 */
export function createRiskControllerTool(qv2: QuantsysV2Client) {
  const tool = new RiskControllerTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { RiskControllerTool } from './RiskControllerTool';
export type { RiskControllerParams, RiskControllerResult } from './prompt';
