/**
 * CancelPendingOrderTool - 撤销挂单工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { CancelPendingOrderTool } from './CancelPendingOrderTool';

export { cancelPendingOrderPrompt } from './prompt';
export type { CancelPendingOrderParams, CancelPendingOrderResult } from './prompt';
export { CancelPendingOrderTool } from './CancelPendingOrderTool';

/**
 * 创建 DSH 工具
 */
export function createCancelPendingOrderTool(qv2: QuantsysV2Client) {
  const tool = new CancelPendingOrderTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
