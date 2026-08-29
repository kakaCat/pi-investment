/**
 * RiskMetricsTool - 风险指标工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { RiskMetricsTool } from './RiskMetricsTool';

/**
 * 创建风险指标工具实例
 */
export function createRiskMetricsTool(qv2: QuantsysV2Client) {
  const tool = new RiskMetricsTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { RiskMetricsTool } from './RiskMetricsTool';
export type { RiskMetricsParams, RiskMetricsResult } from './prompt';
