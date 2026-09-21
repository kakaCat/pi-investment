/**
 * MarketStyleDetectTool - 市场风格检测工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MarketStyleDetectTool } from './MarketStyleDetectTool';

export { marketStyleDetectPrompt } from './prompt';
export type { MarketStyleDetectParams, MarketStyleDetectResult } from './prompt';
export { MarketStyleDetectTool } from './MarketStyleDetectTool';

/**
 * 创建 DSH 工具
 */
export function createMarketStyleDetectTool(qv2: QuantsysV2Client) {
  const tool = new MarketStyleDetectTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
