/**
 * TradeVerifyTool - 交易对账工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { TradeVerifyTool } from './TradeVerifyTool';

export { tradeVerifyPrompt } from './prompt';
export type { TradeVerifyParams, TradeVerifyResult } from './prompt';
export { TradeVerifyTool } from './TradeVerifyTool';

/**
 * 创建 DSH 工具
 */
export function createTradeVerifyTool(qv2: QuantsysV2Client) {
  const tool = new TradeVerifyTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
