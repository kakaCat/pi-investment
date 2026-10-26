import { TradingPlanTool } from './TradingPlanTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { TradingPlanParams } from './prompt';

export function createTradingPlanTool(qv2: QuantsysV2Client) {
  const tool = new TradingPlanTool(qv2);
  return tool.toDSHToolDefinition();
}
