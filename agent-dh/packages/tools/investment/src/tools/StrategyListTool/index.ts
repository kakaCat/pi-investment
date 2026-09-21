import { StrategyListTool } from './StrategyListTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { StrategyListParams, StrategyListResult, StrategyItem } from './prompt';

export function createStrategyListTool(qv2: QuantsysV2Client) {
  const tool = new StrategyListTool(qv2);
  return tool.toDSHToolDefinition();
}
