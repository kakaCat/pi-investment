import { PoolManageTool } from './PoolManageTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { PoolManageParams, PoolAction } from './prompt';

export function createPoolManageTool(qv2: QuantsysV2Client) {
  const tool = new PoolManageTool(qv2);
  return tool.toDSHToolDefinition();
}
