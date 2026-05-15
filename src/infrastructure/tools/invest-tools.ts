/**
 * Investment Tools - A股投资工具集（重构版）
 *
 * 所有工具已按功能域拆分到子模块：
 * - market-tools: 市场概览、板块、宏观数据
 * - stock-query-tools: 股票信息、价格、历史行情
 * - analysis-tools: 技术分析、估值、质量评分
 * - financial-tools: 财务报表、财务指标
 * - screening-tools: 选股、板块筛选
 * - sentiment-tools: 资金流向、龙虎榜、持股分析
 * - portfolio-tools: 持仓管理、复盘报告
 */

import type { ToolDefinition } from "./index.js";
import { marketTools } from "./invest/market-tools.js";
import { stockQueryTools } from "./invest/stock-query-tools.js";
import { analysisTools } from "./invest/analysis-tools.js";
import { financialTools } from "./invest/financial-tools.js";
import { screeningTools } from "./invest/screening-tools.js";
import { sentimentTools } from "./invest/sentiment-tools.js";
import { portfolioTools } from "./invest/portfolio-tools.js";

// 导出共享工具函数供其他模块使用
export { callPython } from "./shared/python-caller.js";
export { detectMarket, requireAshare, roundN } from "./shared/validators.js";

// ===== Export all investment tools =====
export const investTools: ToolDefinition[] = [
  // Market overview — start here
  ...marketTools,
  // Individual stock research
  ...stockQueryTools,
  // HK-specific analysis & Financial data
  ...financialTools,
  // Analysis
  ...analysisTools,
  // Screening & discovery
  ...screeningTools,
  // Market sentiment & flow
  ...sentimentTools,
  // Portfolio & reviews
  ...portfolioTools,
];

/**
 * 统一的工具调用接口（供 Worker 使用）
 */
export async function callInvestTool(toolName: string, params: any): Promise<string> {
  const tool = investTools.find(t => t.name === toolName);
  if (!tool) {
    throw new Error(`Unknown tool: ${toolName}`);
  }

  // 直接调用 execute，类型断言避免类型检查问题
  const result = await (tool.execute as any)("worker-call", params);

  // 提取文本内容
  if (result.content && Array.isArray(result.content)) {
    const textBlock = result.content.find((c: any) => c.type === "text");
    if (textBlock && "text" in textBlock) {
      return textBlock.text;
    }
  }

  return JSON.stringify(result);
}
