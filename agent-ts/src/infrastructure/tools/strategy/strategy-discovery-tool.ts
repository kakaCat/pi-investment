/**
 * Strategy Discovery Tool - 策略发现工具
 *
 * 自动化策略挖掘和参数优化：
 * - 遍历多个策略原型
 * - 自动参数组合搜索
 * - 多股票池测试
 * - 按Sharpe/收益率排序
 * - 推荐最优策略
 *
 * 应用场景：
 * - 策略开发：快速找到有效策略
 * - 参数优化：自动搜索最优参数
 * - 策略评估：对比多个策略效果
 * - 因子挖掘：发现有效的因子组合
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface StrategyDiscoveryParams {
  action: "run" | "archetypes" | "result";
  symbols?: string[];
  start_date?: string;
  end_date?: string;
  metric?: "sharpe" | "return" | "win_rate";
  max_combinations?: number;
  archetype_filter?: string[];
  run_id?: string;
}

interface StrategyResult {
  archetype: string;
  params: Record<string, any>;
  sharpe: number;
  annual_return: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  rank: number;
}

interface DiscoveryResult {
  run_id?: string;
  status?: string;
  total_tested?: number;
  best_strategies?: StrategyResult[];
  archetypes?: Array<{
    name: string;
    description: string;
    params: Record<string, any>;
  }>;
  [key: string]: any;
}

export const strategyDiscoveryTool: ToolDefinition = {
  name: "strategy_discovery",
  label: "策略发现",
  description:
    "自动化策略挖掘和参数优化工具。" +
    "遍历多个策略原型，自动搜索最优参数组合，按Sharpe/收益率排序。" +
    "适用场景：策略开发、参数优化、策略评估、因子挖掘。",

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("run"),
      Type.Literal("archetypes"),
      Type.Literal("result")
    ], {
      description:
        "操作类型。" +
        "run: 运行策略发现流水线；" +
        "archetypes: 列出所有可用的策略原型；" +
        "result: 查询历史发现结果"
    }),
    symbols: Type.Optional(Type.Array(Type.String(), {
      description: "股票代码列表。例如：['600519.SH', '000858.SZ']"
    })),
    start_date: Type.Optional(Type.String({
      description: "回测开始日期，格式：YYYY-MM-DD。默认：2023-01-01",
      pattern: "^\\d{4}-\\d{2}-\\d{2}$"
    })),
    end_date: Type.Optional(Type.String({
      description: "回测结束日期，格式：YYYY-MM-DD。默认：2025-12-31",
      pattern: "^\\d{4}-\\d{2}-\\d{2}$"
    })),
    metric: Type.Optional(Type.Union([
      Type.Literal("sharpe"),
      Type.Literal("return"),
      Type.Literal("win_rate")
    ], {
      description: "优化目标指标。sharpe: 夏普比率；return: 年化收益率；win_rate: 胜率"
    })),
    max_combinations: Type.Optional(Type.Integer({
      description: "每个策略原型的最大参数组合数。默认：30",
      minimum: 5,
      maximum: 100
    })),
    archetype_filter: Type.Optional(Type.Array(Type.String(), {
      description: "只测试特定的策略原型。不提供则测试全部"
    })),
    run_id: Type.Optional(Type.String({
      description: "历史运行ID（action=result时使用）"
    }))
  }),

  execute: async (_toolCallId: string, params: StrategyDiscoveryParams) => {
    try {
      const { action, ...otherParams } = params;

      // 构建API命令
      let command: string;
      let apiParams: any;

      if (action === "run") {
        command = "discovery.run";
        apiParams = {
          symbols: otherParams.symbols,
          start_date: otherParams.start_date,
          end_date: otherParams.end_date,
          metric: otherParams.metric,
          max_combinations: otherParams.max_combinations,
          archetype_filter: otherParams.archetype_filter
        };
      } else if (action === "archetypes") {
        command = "discovery.archetypes";
        apiParams = {};
      } else if (action === "result") {
        if (!otherParams.run_id) {
          throw new Error("查询结果时必须提供 run_id");
        }
        command = "discovery.result";
        apiParams = { run_id: otherParams.run_id };
      } else {
        throw new Error(`未知的操作类型: ${action}`);
      }

      // 调用 quantsys-v2 API
      const result = await runQuantV2(command, apiParams);

      if (!result.ok) {
        const errorMsg = typeof (result as any).error === 'string'
          ? (result as any).error
          : (result as any).error?.message || "策略发现失败";
        throw new Error(errorMsg);
      }

      // 格式化输出
      const formattedOutput = formatDiscoveryResult(
        action,
        (result as any).data as DiscoveryResult,
        params
      );

      return {
        content: [{
          type: "text" as const,
          text: formattedOutput
        }],
        details: (result as any).data
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 策略发现失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化策略发现结果
 */
function formatDiscoveryResult(
  action: string,
  data: DiscoveryResult,
  params: StrategyDiscoveryParams
): string {
  if (!data) {
    return "❌ 未获取到策略发现数据";
  }

  let output = "🔍 **策略发现报告**\n\n";

  if (action === "run") {
    output += formatRunResult(data, params);
  } else if (action === "archetypes") {
    output += formatArchetypes(data);
  } else if (action === "result") {
    output += formatHistoryResult(data);
  }

  return output;
}

/**
 * 格式化运行结果
 */
function formatRunResult(data: DiscoveryResult, params: StrategyDiscoveryParams): string {
  let output = "";

  // 运行信息
  output += `### 运行信息\n\n`;
  if ((data as any).run_id) {
    output += `- **运行ID**：${data.run_id}\n`;
  }
  if ((data as any).status) {
    output += `- **状态**：${getStatusText(data.status || "")}\n`;
  }
  if (params.symbols) {
    output += `- **测试股票**：${params.symbols.join(", ")}\n`;
  }
  if (params.start_date! && params.end_date!) {
    output += `- **回测周期**：${params.start_date!} 至 ${params.end_date!}\n`;
  }
  if (data.total_tested !== undefined) {
    output += `- **测试组合数**：${data.total_tested}个\n`;
  }
  if (params.metric) {
    output += `- **优化指标**：${getMetricName(params.metric)}\n`;
  }
  output += "\n";

  // 发现的最优策略
  if (data.best_strategies && data.best_strategies.length > 0) {
    output += `### 🏆 发现的最优策略（Top ${Math.min(10, data.best_strategies.length)}）\n\n`;
    output += formatStrategyTable(data.best_strategies.slice(0, 10));

    // 最佳策略详情
    const best = data.best_strategies[0];
    output += `### ⭐ 推荐策略\n\n`;
    output += `**策略原型**：${best.archetype}\n`;
    output += `**参数配置**：\n`;
    for (const [key, value] of Object.entries(best.params)) {
      output += `  - ${key}: ${value}\n`;
    }
    output += "\n";

    output += `**绩效指标**：\n`;
    output += `- **Sharpe比率**：${best.sharpe.toFixed(2)}\n`;
    output += `- **年化收益率**：${(best.annual_return * 100).toFixed(2)}%\n`;
    output += `- **最大回撤**：${(best.max_drawdown * 100).toFixed(2)}%\n`;
    output += `- **胜率**：${(best.win_rate * 100).toFixed(1)}%\n`;
    output += `- **总交易次数**：${best.total_trades}次\n\n`;

    // 策略评估
    output += `**策略评估**：\n`;
    output += evaluateStrategy(best);
    output += "\n";

  } else {
    output += `⚠️ 未发现有效策略，建议调整参数或更换股票池\n\n`;
  }

  return output;
}

/**
 * 格式化策略表格
 */
function formatStrategyTable(strategies: StrategyResult[]): string {
  let output = "| 排名 | 策略原型 | Sharpe | 年化收益 | 最大回撤 | 胜率 | 交易次数 |\n";
  output += "|------|----------|--------|----------|----------|------|----------|\n";

  for (const strategy of strategies) {
    const sharpe = strategy.sharpe.toFixed(2);
    const returns = (strategy.annual_return * 100).toFixed(1);
    const drawdown = (strategy.max_drawdown * 100).toFixed(1);
    const winRate = (strategy.win_rate * 100).toFixed(1);

    output += `| ${strategy.rank} | ${strategy.archetype} | ${sharpe} | ${returns}% | ${drawdown}% | ${winRate}% | ${strategy.total_trades} |\n`;
  }

  output += "\n";
  return output;
}

/**
 * 格式化策略原型列表
 */
function formatArchetypes(data: DiscoveryResult): string {
  let output = `### 📚 可用的策略原型\n\n`;

  if (!data.archetypes || data.archetypes.length === 0) {
    return output + "暂无可用的策略原型\n\n";
  }

  output += `**共 ${data.archetypes.length} 个策略原型**\n\n`;

  for (let i = 0; i < data.archetypes.length; i++) {
    const arch = data.archetypes[i];
    output += `#### ${i + 1}. ${arch.name}\n\n`;
    output += `**描述**：${arch.description}\n\n`;

    if (arch.params && Object.keys(arch.params).length > 0) {
      output += `**参数**：\n`;
      for (const [key, value] of Object.entries(arch.params)) {
        output += `  - ${key}: ${JSON.stringify(value)}\n`;
      }
      output += "\n";
    }
  }

  return output;
}

/**
 * 格式化历史结果
 */
function formatHistoryResult(data: DiscoveryResult): string {
  let output = `### 📋 历史运行结果\n\n`;

  if ((data as any).run_id) {
    output += `**运行ID**：${data.run_id}\n\n`;
  }

  if (data.best_strategies && data.best_strategies.length > 0) {
    output += formatStrategyTable(data.best_strategies);
  } else {
    output += "该运行未发现有效策略\n\n";
  }

  return output;
}

/**
 * 评估策略
 */
function evaluateStrategy(strategy: StrategyResult): string {
  const insights: string[] = [];

  // Sharpe评估
  if (strategy.sharpe > 2.0) {
    insights.push("✅ **Sharpe比率优秀**（>2.0）：风险调整后收益非常好");
  } else if (strategy.sharpe > 1.0) {
    insights.push("✅ **Sharpe比率良好**（>1.0）：风险调整后收益可接受");
  } else if (strategy.sharpe > 0.5) {
    insights.push("⚠️ **Sharpe比率一般**（>0.5）：收益与风险比例较低");
  } else {
    insights.push("❌ **Sharpe比率较差**（<0.5）：风险过高，不建议使用");
  }

  // 收益率评估
  if (strategy.annual_return > 0.3) {
    insights.push("✅ **年化收益率高**（>30%）：盈利能力强");
  } else if (strategy.annual_return > 0.15) {
    insights.push("✅ **年化收益率良好**（>15%）：盈利能力可接受");
  } else if (strategy.annual_return > 0) {
    insights.push("⚠️ **年化收益率一般**（>0%）：盈利能力较弱");
  } else {
    insights.push("❌ **年化收益率为负**：策略亏损，不建议使用");
  }

  // 回撤评估
  if (Math.abs(strategy.max_drawdown) < 0.1) {
    insights.push("✅ **最大回撤小**（<10%）：风险控制良好");
  } else if (Math.abs(strategy.max_drawdown) < 0.2) {
    insights.push("⚠️ **最大回撤中等**（<20%）：需要注意风险");
  } else {
    insights.push("❌ **最大回撤大**（>20%）：风险较高，建议优化");
  }

  // 胜率评估
  if (strategy.win_rate > 0.6) {
    insights.push("✅ **胜率高**（>60%）：交易成功率高");
  } else if (strategy.win_rate > 0.5) {
    insights.push("✅ **胜率中等**（>50%）：胜负基本均衡");
  } else {
    insights.push("⚠️ **胜率低**（<50%）：需要提高交易准确性");
  }

  // 交易频率评估
  if (strategy.total_trades < 10) {
    insights.push("⚠️ **交易次数少**（<10次）：样本不足，结果可能不可靠");
  } else if (strategy.total_trades > 100) {
    insights.push("💡 **交易频繁**（>100次）：适合短线交易");
  } else {
    insights.push("💡 **交易适中**（10-100次）：样本量充足");
  }

  return insights.map(s => `- ${s}`).join('\n') + '\n';
}

/**
 * 获取状态文本
 */
function getStatusText(status: string): string {
  const statusMap: Record<string, string> = {
    "running": "🔄 运行中",
    "completed": "✅ 已完成",
    "failed": "❌ 失败",
    "pending": "⏳ 等待中"
  };
  return statusMap[status] || status;
}

/**
 * 获取指标名称
 */
function getMetricName(metric: string): string {
  const metricMap: Record<string, string> = {
    "sharpe": "Sharpe比率",
    "return": "年化收益率",
    "win_rate": "胜率"
  };
  return metricMap[metric] || metric;
}
