/**
 * TradeMonitorTool - 交易监控工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { TradeMonitorTool } from './TradeMonitorTool';

export { tradeMonitorPrompt } from './prompt';
export type { TradeMonitorParams, TradeMonitorResult } from './prompt';
export { TradeMonitorTool } from './TradeMonitorTool';

/**
 * 创建 DSH 工具
 */
export function createTradeMonitorTool(qv2: QuantsysV2Client) {
  const tool = new TradeMonitorTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
