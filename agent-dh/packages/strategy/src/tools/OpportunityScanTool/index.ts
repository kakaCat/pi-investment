/**
 * OpportunityScanTool factory
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OpportunityScanTool } from './OpportunityScanTool';

export function createOpportunityScanTool(qv2: QuantsysV2Client) {
  const tool = new OpportunityScanTool(qv2);
  return tool.toDSHToolDefinition();
}

export { OpportunityScanTool } from './OpportunityScanTool';
export { opportunityScanPrompt } from './prompt';
export type { OpportunityScanParams, OpportunityScanResult } from './prompt';
