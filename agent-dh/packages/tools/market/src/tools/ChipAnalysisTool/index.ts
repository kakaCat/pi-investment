/**
 * ChipAnalysisTool - 筹码分析工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { ChipAnalysisTool } from './ChipAnalysisTool';

export { chipAnalysisPrompt } from './prompt';
export type { ChipAnalysisParams, ChipAnalysisResult } from './prompt';
export { ChipAnalysisTool } from './ChipAnalysisTool';

/**
 * 创建 DSH 工具
 */
export function createChipAnalysisTool(qv2: QuantsysV2Client) {
  const tool = new ChipAnalysisTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
