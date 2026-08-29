/**
 * RotationProposalTool factory
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { RotationProposalTool } from './RotationProposalTool';

export function createRotationProposalTool(qv2: QuantsysV2Client) {
  const tool = new RotationProposalTool(qv2);
  return tool.toDSHToolDefinition();
}

export { RotationProposalTool } from './RotationProposalTool';
export { rotationProposalPrompt } from './prompt';
export type { RotationProposalParams, RotationProposalResult } from './prompt';
