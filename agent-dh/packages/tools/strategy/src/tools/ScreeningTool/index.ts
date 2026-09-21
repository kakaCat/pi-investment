/**
 * ScreeningTool factory
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { ScreeningTool } from './ScreeningTool';

export function createScreeningTool(qv2: QuantsysV2Client) {
  const tool = new ScreeningTool(qv2);
  return tool.toDSHToolDefinition();
}

export { ScreeningTool } from './ScreeningTool';
export { screeningPrompt } from './prompt';
export type { ScreeningParams, ScreeningResult } from './prompt';
