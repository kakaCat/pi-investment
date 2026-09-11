import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { StockEventsTool } from './StockEventsTool';
export { stockEventsPrompt } from './prompt';
export type { StockEventsParams } from './prompt';
export { StockEventsTool } from './StockEventsTool';
export function createStockEventsTool(qv2: QuantsysV2Client) {
  const tool = new StockEventsTool(qv2);
  return tool.toDSHToolDefinition() as any;
}
