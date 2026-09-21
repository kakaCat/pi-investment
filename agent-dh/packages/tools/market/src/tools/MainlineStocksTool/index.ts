/**
 * MainlineStocksTool - 主线个股明细查询工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MainlineStocksTool } from './MainlineStocksTool';

/**
 * 创建主线个股明细查询工具实例
 */
export function createMainlineStocksTool(qv2: QuantsysV2Client) {
  const tool = new MainlineStocksTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { MainlineStocksTool } from './MainlineStocksTool';
export type { MainlineStocksParams, MainlineStocksResult } from './prompt';
