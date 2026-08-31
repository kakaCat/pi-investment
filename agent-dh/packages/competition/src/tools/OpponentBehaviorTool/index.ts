import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OpponentBehaviorTool } from './OpponentBehaviorTool';

export * from './OpponentBehaviorTool';
export * from './prompt';

/**
 * Create Opponent Behavior Tool
 */
export function createOpponentBehaviorTool(qv2: QuantsysV2Client) {
  const tool = new OpponentBehaviorTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}
