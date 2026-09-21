/**
 * SectorAnalysisTool - 行业分析工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { SectorAnalysisTool } from './SectorAnalysisTool';

export { sectorAnalysisPrompt } from './prompt';
export type { SectorAnalysisParams, SectorAnalysisResult } from './prompt';
export { SectorAnalysisTool } from './SectorAnalysisTool';

/**
 * 创建 DSH 工具
 */
export function createSectorAnalysisTool(qv2: QuantsysV2Client) {
  const tool = new SectorAnalysisTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
