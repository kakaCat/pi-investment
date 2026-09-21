/**
 * DataFetchKlineTool - 导出工厂函数
 */

import { DataFetchKlineTool } from './DataFetchKlineTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

// 导出类型
export type { DataFetchKlineParams, DataFetchKlineResult, KlineData } from './prompt';

/**
 * 创建 DSH 工具
 */
export function createDataFetchKlineTool(qv2: QuantsysV2Client) {
  const tool = new DataFetchKlineTool(qv2);
  return tool.toDSHToolDefinition();
}
