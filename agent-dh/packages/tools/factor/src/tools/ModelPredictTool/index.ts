/**
 * ModelPredictTool - ML 模型上涨概率预测
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { ModelPredictTool } from './ModelPredictTool';

export { modelPredictPrompt } from './prompt';
export type { ModelPredictParams } from './prompt';
export { ModelPredictTool } from './ModelPredictTool';

export function createModelPredictTool(qv2: QuantsysV2Client) {
  const tool = new ModelPredictTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
