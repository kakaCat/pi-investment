/**
 * PePercentileTool - PE 历史分位工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { PePercentileTool } from './PePercentileTool';

export { pePercentilePrompt } from './prompt';
export type { PePercentileParams } from './prompt';
export { PePercentileTool } from './PePercentileTool';

export function createPePercentileTool(qv2: QuantsysV2Client) {
  const tool = new PePercentileTool(qv2);
  return tool.toDSHToolDefinition() as any;
}
