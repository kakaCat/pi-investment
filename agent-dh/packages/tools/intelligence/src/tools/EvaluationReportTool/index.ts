import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { EvaluationReportTool } from './EvaluationReportTool';

export { evaluationReportPrompt, renderEvaluationReport } from './prompt';
export type { EvaluationReportParams } from './prompt';
export { EvaluationReportTool } from './EvaluationReportTool';

export function createEvaluationReportTool(qv2: QuantsysV2Client) {
  const tool = new EvaluationReportTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
