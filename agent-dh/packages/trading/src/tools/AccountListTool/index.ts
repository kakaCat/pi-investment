/**
 * AccountListTool - 账户清单工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { AccountListTool } from './AccountListTool';

export { accountListPrompt } from './prompt';
export type { AccountListParams, AccountListResult } from './prompt';
export { AccountListTool } from './AccountListTool';

export function createAccountListTool(qv2: QuantsysV2Client) {
  const tool = new AccountListTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
