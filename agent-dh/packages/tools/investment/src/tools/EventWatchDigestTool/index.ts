import { EventWatchDigestTool } from './EventWatchDigestTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { EventWatchDigestParams } from './prompt';

export function createEventWatchDigestTool(qv2: QuantsysV2Client) {
  const tool = new EventWatchDigestTool(qv2);
  return tool.toDSHToolDefinition();
}
