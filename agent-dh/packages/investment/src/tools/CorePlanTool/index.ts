import { CorePlanTool } from './CorePlanTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { CorePlanParams, CorePlanResult } from './prompt';

export function createCorePlanTool(qv2: QuantsysV2Client) {
  const tool = new CorePlanTool(qv2);
  return tool.toDSHToolDefinition();
}
