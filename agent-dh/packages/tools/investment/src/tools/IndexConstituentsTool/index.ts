/**
 * IndexConstituentsTool - 指数成分股（基准成分池）
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { IndexConstituentsTool } from './IndexConstituentsTool';

export { indexConstituentsPrompt } from './prompt';
export type { IndexConstituentsParams, IndexConstituentsResult } from './prompt';
export { IndexConstituentsTool } from './IndexConstituentsTool';

export function createIndexConstituentsTool(qv2: QuantsysV2Client) {
  const tool = new IndexConstituentsTool(qv2);
  return tool.toDSHToolDefinition() as any;
}
