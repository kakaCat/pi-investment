/**
 * DataFetchQuoteTool - 导出工厂函数
 */

import { DataFetchQuoteTool } from './DataFetchQuoteTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

// 导出类型
export { DataFetchQuoteParams, DataFetchQuoteResult } from './prompt';

/**
 * 创建 DSH 工具
 */
export function createDataFetchQuoteTool(qv2: QuantsysV2Client) {
  const tool = new DataFetchQuoteTool(qv2);
  return tool.toDSHToolDefinition();
}
