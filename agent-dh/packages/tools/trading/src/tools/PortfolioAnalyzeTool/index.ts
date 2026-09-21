/**
 * PortfolioAnalyzeTool - 持仓健康一键分析
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { PortfolioAnalyzeTool } from './PortfolioAnalyzeTool';

export { portfolioAnalyzePrompt } from './prompt';
export type { PortfolioAnalyzeParams } from './prompt';
export { PortfolioAnalyzeTool } from './PortfolioAnalyzeTool';

export function createPortfolioAnalyzeTool(qv2: QuantsysV2Client) {
  const tool = new PortfolioAnalyzeTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
