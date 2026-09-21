/**
 * SwingPointsTool - ZigZag 波段买卖点分析工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { SwingPointsTool } from './SwingPointsTool';

export { swingPointsPrompt } from './prompt';
export type { SwingPointsParams, SwingPointsResult } from './prompt';
export { SwingPointsTool } from './SwingPointsTool';

/**
 * 创建 DSH 工具
 */
export function createSwingPointsTool(qv2: QuantsysV2Client) {
  const tool = new SwingPointsTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
