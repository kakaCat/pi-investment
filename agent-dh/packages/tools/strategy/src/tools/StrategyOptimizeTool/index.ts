/**
 * StrategyOptimizeTool factory
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { StrategyOptimizeTool } from './StrategyOptimizeTool';

export function createStrategyOptimizeTool(qv2: QuantsysV2Client) {
  const tool = new StrategyOptimizeTool(qv2);
  return tool.toDSHToolDefinition();
}

export { StrategyOptimizeTool } from './StrategyOptimizeTool';
export { strategyOptimizePrompt } from './prompt';
export type { StrategyOptimizeParams, StrategyOptimizeResult } from './prompt';
