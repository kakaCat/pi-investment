/**
 * Portfolio Analyze Tool - 分析持仓并给出建议
 *
 * Agent智能分析当前持仓，判断是否需要操作
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution } from "../shared/error-handler.js";

interface PortfolioAnalyzeInput {
  check_risk?: boolean;
}

async function analyzePortfolio(input: PortfolioAnalyzeInput) {
  try {
    // 获取持仓状态 - 使用simulation账户API
    const response = await fetch('http://127.0.0.1:5001/api/simulation/accounts/default');
    const result = await response.json() as any;

    if (!result.success) {
      return {
        success: false,
        error: '无法获取持仓信息'
      };
    }

    const portfolio = result.data;
    const holdings = portfolio.positions || portfolio.holdings || [];

    // 如果空仓
    if (holdings.length === 0) {
      return {
        success: true,
        message: '当前空仓',
        holdings_count: 0,
        total_pnl_pct: 0,
        analysis: [],
        summary: '当前空仓，可以寻找买入机会',
        suggestion: '建议：使用market_analyze分析市场，然后扫描池寻找高质量买入机会'
      };
    }

    // 分析每个持仓
    const analysis = [];

    for (let holding of holdings) {
      const pnl_pct = holding.profit_rate || holding.pnl_pct || 0;
      const days_held = holding.days_held || 0;

      let action = 'hold';
      let reason = '';
      let priority = 0;  // 优先级：0=持有，1=可选，2=建议，3=强烈建议

      // T+1检查（最高优先级）
      if (days_held === 0) {
        action = 'wait_t1';
        reason = '今日买入，需等待T+1才能卖出';
        priority = 0;
      }
      // 止盈规则
      else if (pnl_pct >= 10) {
        action = 'take_profit';
        reason = `盈利${pnl_pct.toFixed(1)}%，建议止盈`;
        priority = pnl_pct >= 15 ? 3 : 2;
      }
      // 止损规则
      else if (pnl_pct <= -5) {
        action = 'stop_loss';
        reason = `亏损${Math.abs(pnl_pct).toFixed(1)}%，${pnl_pct <= -8 ? '强烈' : ''}建议止损`;
        priority = pnl_pct <= -8 ? 3 : 2;
      }
      // 小盈利
      else if (pnl_pct > 5) {
        action = 'hold';
        reason = `盈利${pnl_pct.toFixed(1)}%，继续持有观察`;
        priority = 0;
      }
      // 小亏损
      else if (pnl_pct < -2) {
        action = 'hold';
        reason = `亏损${Math.abs(pnl_pct).toFixed(1)}%，关注走势，考虑止损`;
        priority = 1;
      }
      // 震荡区间
      else {
        action = 'hold';
        reason = `盈亏${pnl_pct.toFixed(1)}%，继续持有`;
        priority = 0;
      }

      analysis.push({
        symbol: holding.symbol,
        shares: holding.shares,
        cost_price: holding.avg_price || holding.cost_price || holding.cost,
        current_price: holding.current_price,
        pnl: holding.profit || holding.pnl,
        pnl_pct: pnl_pct,
        days_held: days_held,
        action: action,
        reason: reason,
        priority: priority
      });
    }

    // 按优先级排序
    analysis.sort((a, b) => b.priority - a.priority);

    // 生成总结
    const total_pnl_pct = portfolio.cumulative_return || portfolio.totalPnlPct || 0;
    const needs_action = analysis.filter(a => a.priority >= 2);

    let summary = `当前${holdings.length}个持仓，总收益${total_pnl_pct.toFixed(2)}%`;

    if (needs_action.length > 0) {
      summary += `\n建议操作：${needs_action.length}只股票需要关注`;
      needs_action.forEach(a => {
        summary += `\n  - ${a.symbol}: ${a.reason}`;
      });
    }

    return {
      success: true,
      total_pnl_pct: total_pnl_pct,
      holdings_count: holdings.length,
      analysis: analysis,
      needs_action_count: needs_action.length,
      summary: summary,
      suggestion: needs_action.length > 0
        ? `使用portfolio_trade执行${needs_action[0].action === 'take_profit' ? '止盈' : '止损'}操作`
        : '当前持仓正常，继续持有观察即可'
    };

  } catch (error) {
    return {
      success: false,
      error: `分析失败: ${error instanceof Error ? error.message : String(error)}`
    };
  }
}

export const portfolioAnalyzeTool: ToolDefinition = {
  name: "portfolio_analyze",
  label: "分析持仓",
  description:
    "智能分析Agent虚拟仓持仓，给出操作建议。" +
    "\n\n分析内容：" +
    "\n  • 每只股票的盈亏状态" +
    "\n  • 是否需要止盈（盈利≥10%）" +
    "\n  • 是否需要止损（亏损≥5%）" +
    "\n  • T+1限制检查" +
    "\n  • 操作优先级排序" +
    "\n\n返回建议：" +
    "\n  • hold - 继续持有" +
    "\n  • take_profit - 建议止盈" +
    "\n  • stop_loss - 建议止损" +
    "\n  • wait_t1 - 今日买入，等待T+1" +
    "\n\n使用场景：" +
    "\n  • 早盘分析：评估持仓是否需要卖出" +
    "\n  • 每日复盘：检查持仓表现" +
    "\n  • 风险控制：及时止盈止损" +
    "\n\n典型用法：" +
    "\n  portfolio_analyze() - 分析所有持仓" +
    "\n  portfolio_analyze({ check_risk: true }) - 包含风险检查",

  parameters: Type.Object({
    check_risk: Type.Optional(Type.Boolean({
      description: "是否进行风险检查（默认true）",
      default: true
    }))
  }),

  execute: async (toolCallId: string, input: PortfolioAnalyzeInput) => {
    return wrapToolExecution(
      async () => await analyzePortfolio(input),
      { toolName: "portfolio_analyze" }
    );
  }
};
