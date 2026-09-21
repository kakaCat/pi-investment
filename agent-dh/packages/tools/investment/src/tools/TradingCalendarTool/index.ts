import { TradingCalendarTool } from './TradingCalendarTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { TradingCalendarParams, TradingCalendarResult } from './prompt';

export function createTradingCalendarTool(qv2: QuantsysV2Client) {
  const tool = new TradingCalendarTool(qv2);
  return tool.toDSHToolDefinition();
}
