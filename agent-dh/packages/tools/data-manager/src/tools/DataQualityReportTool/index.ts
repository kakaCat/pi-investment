import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { DataQualityReportTool } from './DataQualityReportTool';

/**
 * 创建数据质量报告工具实例
 */
export function createDataQualityReportTool(qv2: QuantsysV2Client) {
  const tool = new DataQualityReportTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { DataQualityReportTool } from './DataQualityReportTool';
export { dataQualityReportPrompt } from './prompt';
export type { DataQualityReportParams, DataQualityReportResult } from './prompt';
