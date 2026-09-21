/**
 * RotationExecuteTool factory
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { RotationExecuteTool } from './RotationExecuteTool';

export function createRotationExecuteTool(qv2: QuantsysV2Client) {
  const tool = new RotationExecuteTool(qv2);
  return tool.toDSHToolDefinition();
}

export { RotationExecuteTool } from './RotationExecuteTool';
export { rotationExecutePrompt } from './prompt';
export type { RotationExecuteParams, RotationExecuteResult } from './prompt';
