/**
 * AccountInfoTool - 账户信息工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { AccountInfoTool } from './AccountInfoTool';

export { accountInfoPrompt } from './prompt';
export type { AccountInfoParams, AccountInfoResult } from './prompt';
export { AccountInfoTool } from './AccountInfoTool';

/**
 * 创建 DSH 工具
 */
export function createAccountInfoTool(qv2: QuantsysV2Client) {
  const tool = new AccountInfoTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
