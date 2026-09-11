/**
 * TradingStatusTool - 交易状态
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { TradingStatusTool } from './TradingStatusTool';

export { tradingStatusPrompt } from './prompt';
export type { TradingStatusParams } from './prompt';
export { TradingStatusTool } from './TradingStatusTool';

export function createTradingStatusTool(qv2: QuantsysV2Client) {
  const tool = new TradingStatusTool(qv2);
  return tool.toDSHToolDefinition() as any;
}
