/**
 * AlgoExecuteTool - 算法交易工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { AlgoExecuteTool } from './AlgoExecuteTool';

export { algoExecutePrompt } from './prompt';
export type { AlgoExecuteParams, AlgoExecuteResult } from './prompt';
export { AlgoExecuteTool } from './AlgoExecuteTool';

/**
 * 创建 DSH 工具
 */
export function createAlgoExecuteTool(qv2: QuantsysV2Client) {
  const tool = new AlgoExecuteTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
