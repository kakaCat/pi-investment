import { EventCalendarTool } from './EventCalendarTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { EventCalendarParams, EventCalendarResult } from './prompt';

export function createEventCalendarTool(qv2: QuantsysV2Client) {
  const tool = new EventCalendarTool(qv2);
  return tool.toDSHToolDefinition();
}
