import { StockIntelTool } from './StockIntelTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { StockIntelParams, StockIntelResult } from './prompt';

export function createStockIntelTool(qv2: QuantsysV2Client) {
  const tool = new StockIntelTool(qv2);
  return tool.toDSHToolDefinition();
}
