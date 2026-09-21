/**
 * MarketAlertTool - 市场异动提醒工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MarketAlertTool } from './MarketAlertTool';

/**
 * 创建市场异动提醒工具实例
 */
export function createMarketAlertTool(qv2: QuantsysV2Client) {
  const tool = new MarketAlertTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { MarketAlertTool } from './MarketAlertTool';
export type { MarketAlertParams } from './prompt';
