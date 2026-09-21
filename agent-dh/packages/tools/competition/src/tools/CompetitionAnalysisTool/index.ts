import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { CompetitionAnalysisTool } from './CompetitionAnalysisTool';

export * from './CompetitionAnalysisTool';
export * from './prompt';

/**
 * Create Competition Analysis Tool
 *
 * Factory function following the standard pattern
 */
export function createCompetitionAnalysisTool(qv2: QuantsysV2Client) {
  const tool = new CompetitionAnalysisTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}
