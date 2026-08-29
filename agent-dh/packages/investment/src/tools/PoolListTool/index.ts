import { PoolListTool } from './PoolListTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export { PoolListParams, PoolListResult, PoolItem } from './prompt';

export function createPoolListTool(qv2: QuantsysV2Client) {
  const tool = new PoolListTool(qv2);
  return tool.toDSHToolDefinition();
}
