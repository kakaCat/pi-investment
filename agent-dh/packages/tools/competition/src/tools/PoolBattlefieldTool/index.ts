import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { PoolBattlefieldTool } from './PoolBattlefieldTool';

export * from './PoolBattlefieldTool';
export * from './prompt';

/**
 * Create Pool Battlefield Tool（M2-3）
 */
export function createPoolBattlefieldTool(qv2: QuantsysV2Client) {
  const tool = new PoolBattlefieldTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}
