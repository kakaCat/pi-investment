/**
 * MinuteKlineTool - 分钟线
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { MinuteKlineTool } from './MinuteKlineTool';

export { minuteKlinePrompt } from './prompt';
export type { MinuteKlineParams } from './prompt';
export { MinuteKlineTool } from './MinuteKlineTool';

export function createMinuteKlineTool(qv2: QuantsysV2Client) {
  const tool = new MinuteKlineTool(qv2);
  return tool.toDSHToolDefinition() as any;
}
