/**
 * RotationSimulateTool factory
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { RotationSimulateTool } from './RotationSimulateTool';

export function createRotationSimulateTool(qv2: QuantsysV2Client) {
  const tool = new RotationSimulateTool(qv2);
  return tool.toDSHToolDefinition();
}

export { RotationSimulateTool } from './RotationSimulateTool';
export { rotationSimulatePrompt } from './prompt';
export type { RotationSimulateParams, RotationSimulateResult } from './prompt';
