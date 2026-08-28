/**
 * PortfolioTradeTool - 导出和 DSH 适配器
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { PortfolioTradeTool } from './PortfolioTradeTool';

export { PortfolioTradeTool } from './PortfolioTradeTool';
export { portfolioTradePrompt } from './prompt';
export type { PortfolioTradeParams, PortfolioTradeResult } from './prompt';

/**
 * 创建 DSH 工具
 */
export function createPortfolioTradeTool(qv2: QuantsysV2Client, osMemory: any, ctx: any) {
  const tool = new PortfolioTradeTool(qv2, osMemory, ctx);

  // 使用 BaseTool 的 toDSHToolDefinition() 方法转换为 DSH 格式
  return defineTool(tool.toDSHToolDefinition() as any);
}
