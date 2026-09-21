/**
 * StrategyExecuteTool factory
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { StrategyExecuteTool } from './StrategyExecuteTool';

export function createStrategyExecuteTool(qv2: QuantsysV2Client) {
  const tool = new StrategyExecuteTool(qv2);
  return tool.toDSHToolDefinition();
}

export { StrategyExecuteTool } from './StrategyExecuteTool';
export { strategyExecutePrompt } from './prompt';
export type { StrategyExecuteParams, StrategyExecuteResult } from './prompt';
