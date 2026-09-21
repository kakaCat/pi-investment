/**
 * PositionListTool - 持仓列表工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { PositionListTool } from './PositionListTool';

export { positionListPrompt } from './prompt';
export type { PositionListParams, PositionListResult, PositionItem } from './prompt';
export { PositionListTool } from './PositionListTool';

/**
 * 创建 DSH 工具
 */
export function createPositionListTool(qv2: QuantsysV2Client) {
  const tool = new PositionListTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
