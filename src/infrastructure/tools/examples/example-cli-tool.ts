/**
 * Example Tool - 展示所有新功能的完整示例
 *
 * 这个示例工具展示了如何使用新的工具基础设施：
 * - 统一的输出格式化
 * - 统一的错误处理
 * - 性能监控
 * - 参数验证
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import {
  wrapToolExecution,
  validateParams
} from "../shared/error-handler.js";
import {
  formatTableOutput,
  formatKeyValueOutput,
  formatListOutput,
  Column
} from "../shared/output-formatters.js";

// 模拟数据服务
async function fetchStockList(market?: string): Promise<any[]> {
  // 实际项目中，这里会调用真实API
  return [
    { symbol: '600000', name: '浦发银行', price: 10.50, change_pct: 0.0234 },
    { symbol: '600519', name: '贵州茅台', price: 1850.00, change_pct: 0.0156 },
    { symbol: '000001', name: '平安银行', price: 12.30, change_pct: -0.0089 }
  ].filter(s => !market || s.symbol.startsWith(market === '沪市' ? '6' : '0'));
}

async function fetchStockDetail(symbol: string): Promise<any> {
  // 实际项目中，这里会调用真实API
  return {
    symbol,
    name: '浦发银行',
    price: 10.50,
    change_pct: 0.0234,
    volume: 12345678,
    market_cap: 3000000000,
    pe: 5.6,
    pb: 0.52,
    roe: 0.12
  };
}

/**
 * 示例CLI工具定义
 */
export const exampleCliTool: ToolDefinition = {
  name: "example_cli",
  label: "示例CLI工具",
  description:
    "这是一个示例工具，展示如何使用新的工具基础设施。" +
    "支持的命令：list（列表）、detail（详情）、demo（演示）。" +
    "集成了统一的错误处理、性能监控和输出格式化。",

  // 参数定义（使用TypeBox）
  parameters: Type.Object({
    command: Type.Union([
      Type.Literal("list"),
      Type.Literal("detail"),
      Type.Literal("demo")
    ], { description: "命令名称" }),

    params: Type.Optional(
      Type.Object({
        symbol: Type.Optional(Type.String({ description: "股票代码" })),
        market: Type.Optional(Type.String({ description: "市场类型" })),
        format: Type.Optional(Type.String({ description: "输出格式" }))
      })
    )
  }),

  // 工具执行函数
  execute: async (_toolCallId, input: any) => {
    return wrapToolExecution(
      async () => {
        const { command, params = {} } = input as {
          command: string;
          params?: Record<string, any>
        };

        // 根据命令执行不同逻辑
        switch (command) {
          case "list":
            return handleList(params);

          case "detail":
            return handleDetail(params);

          case "demo":
            return handleDemo(params);

          default:
            throw new Error(`未知命令: ${command}`);
        }
      },
      {
        toolName: "example_cli",
        enablePerformanceMonitoring: true,
        slowToolThreshold: 3000, // 3秒算慢
        errorSuggestion: "请检查命令和参数是否正确。支持的命令：list, detail, demo"
      }
    );
  }
};

/**
 * 处理 list 命令
 * 展示：表格格式化、参数验证
 */
async function handleList(params: Record<string, any>) {
  // 参数验证（可选）
  if (params.market) {
    validateParams(params)
      .enum('market', ['沪市', '深市', '全部'])
      .validate();
  }

  // 获取数据
  const stocks = await fetchStockList(params.market);

  // 使用表格格式化
  const columns: Column[] = [
    {
      key: 'symbol',
      label: '代码',
      width: 10
    },
    {
      key: 'name',
      label: '名称',
      width: 12
    },
    {
      key: 'price',
      label: '价格',
      width: 10,
      align: 'right',
      format: (v) => `¥${v.toFixed(2)}`
    },
    {
      key: 'change_pct',
      label: '涨跌幅',
      width: 10,
      align: 'right',
      format: (v) => {
        const pct = (v * 100).toFixed(2);
        return v >= 0 ? `+${pct}%` : `${pct}%`;
      }
    }
  ];

  const text = formatTableOutput(stocks, columns, {
    title: params.market ? `${params.market}股票列表` : '股票列表',
    maxRows: 50,
    showIndex: true,
    emptyMessage: '暂无数据'
  });

  return {
    content: [{ type: "text" as const, text }],
    details: stocks
  };
}

/**
 * 处理 detail 命令
 * 展示：键值对格式化、必填参数验证
 */
async function handleDetail(params: Record<string, any>) {
  // 验证必填参数
  validateParams(params)
    .required(['symbol'])
    .types({ symbol: 'string' })
    .validate();

  // 获取数据
  const detail = await fetchStockDetail(params.symbol);

  // 使用键值对格式化
  const text = formatKeyValueOutput(detail, {
    title: '股票详情',
    keyWidth: 15,
    formatter: {
      price: (v) => `¥${v.toFixed(2)}`,
      change_pct: (v) => `${(v * 100).toFixed(2)}%`,
      volume: (v) => v.toLocaleString('zh-CN'),
      market_cap: (v) => `${(v / 100000000).toFixed(2)}亿`,
      pe: (v) => v.toFixed(2),
      pb: (v) => v.toFixed(2),
      roe: (v) => `${(v * 100).toFixed(2)}%`
    }
  });

  return {
    content: [{ type: "text" as const, text }],
    details: detail
  };
}

/**
 * 处理 demo 命令
 * 展示：列表格式化、多种格式组合
 */
async function handleDemo(params: Record<string, any>) {
  const sections: string[] = [];

  // 1. 列表格式化示例
  const features = [
    '统一的错误处理',
    '自动性能监控',
    '链式参数验证',
    '多种输出格式',
    '工具统计追踪'
  ];

  sections.push(formatListOutput(features, {
    title: '工具特性',
    bullet: '✓',
    maxItems: 10
  }));

  // 2. 键值对格式化示例
  const stats = {
    totalCalls: 150,
    successCalls: 145,
    failureCalls: 5,
    avgDuration: 233,
    successRate: 0.9667
  };

  sections.push(formatKeyValueOutput(stats, {
    title: '工具统计',
    keyWidth: 20,
    formatter: {
      avgDuration: (v) => `${v}ms`,
      successRate: (v) => `${(v * 100).toFixed(2)}%`
    }
  }));

  // 3. 表格格式化示例
  const samples = [
    { command: 'list', count: 50, avgTime: 234 },
    { command: 'detail', count: 80, avgTime: 189 },
    { command: 'demo', count: 20, avgTime: 156 }
  ];

  const columns: Column[] = [
    { key: 'command', label: '命令', width: 12 },
    { key: 'count', label: '调用次数', width: 10, align: 'right' },
    { key: 'avgTime', label: '平均耗时', width: 12, align: 'right', format: (v) => `${v}ms` }
  ];

  sections.push(formatTableOutput(samples, columns, {
    title: '命令使用统计',
    showIndex: false
  }));

  const text = sections.join('\n\n');

  return {
    content: [{ type: "text" as const, text }],
    details: { features, stats, samples }
  };
}

// 导出示例（用于测试）
export const exampleCommands = {
  list: { command: "list", params: { market: "沪市" } },
  detail: { command: "detail", params: { symbol: "600000" } },
  demo: { command: "demo" }
};
