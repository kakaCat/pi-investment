import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";

const V2_API_BASE = process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001";

async function apiCall(method: string, path: string, data?: any): Promise<any> {
  const url = `${V2_API_BASE}${path}`;
  const options: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" }
  };

  if (data) {
    if (method === "GET") {
      const params = new URLSearchParams(data);
      return fetch(`${url}?${params}`, options).then(r => r.json());
    } else {
      options.body = JSON.stringify(data);
    }
  }

  const response = await fetch(url, options);
  return response.json();
}

export const signalExecutionTool: ToolDefinition = {
  name: "signal_execution",
  label: "信号执行管理",
  description: `信号执行管理工具

支持的操作：
- trigger: 手动触发信号执行流程
- status: 查询最近的执行状态
- logs: 查询执行日志
- statistics: 查询执行统计
- config: 查询/更新风控配置`,

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("trigger"),
      Type.Literal("status"),
      Type.Literal("logs"),
      Type.Literal("statistics"),
      Type.Literal("config")
    ]),
    days: Type.Optional(Type.Number({ minimum: 1, maximum: 90 })),
    execution_date: Type.Optional(Type.String()),
    config_updates: Type.Optional(Type.Object({}, { additionalProperties: true }))
  }),

  execute: async (_toolCallId, params: any) => {
    const { action, days, execution_date, config_updates } = params;

    try {
      let text: string;
      switch (action) {
        case "trigger":
          text = await handleTrigger(execution_date);
          break;
        case "status":
          text = await handleStatus();
          break;
        case "logs":
          text = await handleLogs(days || 7);
          break;
        case "statistics":
          text = await handleStatistics(days || 30);
          break;
        case "config":
          if (config_updates) {
            text = await handleConfigUpdate(config_updates);
          } else {
            text = await handleConfigQuery();
          }
          break;
        default:
          text = `❌ 未知操作: ${action}`;
      }

      return {
        content: [{ type: "text" as const, text }],
        details: undefined
      };
    } catch (error: any) {
      return {
        content: [{ type: "text" as const, text: `❌ 执行失败: ${error.message}` }],
        details: undefined
      };
    }
  }
};

async function handleTrigger(execution_date?: string): Promise<string> {
  const response = await apiCall('POST', '/api/signal-execution/trigger', {
    execution_date
  });

  if (!response.success) {
    return `❌ 触发失败: ${response.error}`;
  }

  const result = response.data;

  return `## ✅ 信号执行完成

**执行日期**: ${result.execution_date}
**执行耗时**: ${result.duration_ms}ms

### 📊 执行统计

| 项目 | 数量 |
|------|------|
| 运行策略 | ${result.strategies_run} |
| 生成信号 | ${result.signals_generated} |
| 通过风控 | ${result.signals_approved} |
| 风控拒绝 | ${result.signals_rejected} |
| 创建订单 | ${result.orders_created} |`;
}

async function handleStatus(): Promise<string> {
  const response = await apiCall('GET', '/api/signal-execution/logs', {
    page: '1',
    page_size: '1'
  });

  if (!response.success) {
    return `❌ 查询失败: ${response.error}`;
  }

  const logs = response.data.items;
  if (logs.length === 0) {
    return `📭 暂无执行记录`;
  }

  const latest = logs[0];
  const statusEmoji = latest.status === 'completed' ? '✅' :
                      latest.status === 'failed' ? '❌' : '⏳';

  return `## ${statusEmoji} 最近执行状态

**执行日期**: ${latest.execution_date}
**状态**: ${latest.status}
**耗时**: ${latest.duration_ms}ms

### 统计
- 运行策略: ${latest.strategies_run}
- 生成信号: ${latest.signals_generated}
- 通过风控: ${latest.signals_approved}
- 风控拒绝: ${latest.signals_rejected}
- 创建订单: ${latest.orders_created}
- 错误数: ${latest.errors_count}`;
}

async function handleLogs(days: number): Promise<string> {
  const endDate = new Date().toISOString().split('T')[0];
  const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000)
    .toISOString().split('T')[0];

  const response = await apiCall('GET', '/api/signal-execution/logs', {
    start_date: startDate,
    end_date: endDate,
    page: '1',
    page_size: '20'
  });

  if (!response.success) {
    return `❌ 查询失败: ${response.error}`;
  }

  const { items, total } = response.data;

  if (items.length === 0) {
    return `📭 最近 ${days} 天无执行记录`;
  }

  let output = `## 📋 执行日志（最近 ${days} 天）\n\n`;
  output += `共 ${total} 条记录\n\n`;
  output += `| 日期 | 状态 | 策略 | 信号 | 订单 | 耗时 |\n`;
  output += `|------|------|------|------|------|------|\n`;

  for (const log of items) {
    const statusEmoji = log.status === 'completed' ? '✅' :
                        log.status === 'failed' ? '❌' : '⏳';
    output += `| ${log.execution_date} | ${statusEmoji} ${log.status} | ${log.strategies_run} | ${log.signals_generated} | ${log.orders_created} | ${log.duration_ms}ms |\n`;
  }

  return output;
}

async function handleStatistics(days: number): Promise<string> {
  const response = await apiCall('GET', '/api/signal-execution/statistics', {
    days: days.toString()
  });

  if (!response.success) {
    return `❌ 查询失败: ${response.error}`;
  }

  const stats = response.data;

  return `## 📊 执行统计（最近 ${days} 天）

### 总体统计
- 总执行次数: ${stats.total_executions}
- 成功次数: ${stats.successful_executions}
- 失败次数: ${stats.failed_executions}
- 成功率: ${stats.success_rate}%

### 信号统计
- 总生成信号: ${stats.total_signals_generated}
- 总通过风控: ${stats.total_signals_approved}
- 总被拒绝: ${stats.total_signals_rejected}
- 通过率: ${stats.approval_rate}%

### 订单统计
- 总创建订单: ${stats.total_orders_created}
- 平均每次: ${stats.avg_orders_per_execution}

### 性能统计
- 平均耗时: ${stats.avg_duration_ms}ms
- 最长耗时: ${stats.max_duration_ms}ms
- 最短耗时: ${stats.min_duration_ms}ms`;
}

async function handleConfigQuery(): Promise<string> {
  const response = await apiCall('GET', '/api/signal-execution/config', {});

  if (!response.success) {
    return `❌ 查询失败: ${response.error}`;
  }

  const config = response.data;

  return `## ⚙️ 风控配置

### 订单限制
- 单笔订单上限: ${config.max_single_order_percent}%
- 最低现金储备: ${config.min_cash_reserve_percent}%

### 仓位限制
- 单只股票上限: ${config.max_position_percent}%
- 单个行业上限: ${config.max_sector_percent}%
- 总仓位上限: ${config.max_total_position_percent}%

### 交易限制
- 日内总交易次数: ${config.max_daily_trades}
- 单只股票日内交易: ${config.max_single_stock_trades}

### 止损设置
- 是否强制止损: ${config.require_stop_loss ? '是' : '否'}
- 最小止损幅度: ${config.min_stop_loss_percent}%
- 最大止损幅度: ${config.max_stop_loss_percent}%`;
}

async function handleConfigUpdate(updates: any): Promise<string> {
  const response = await apiCall('PUT', '/api/signal-execution/config', updates);

  if (!response.success) {
    return `❌ 更新失败: ${response.error}`;
  }

  return `✅ 风控配置已更新

更新的字段:
${Object.entries(updates).map(([key, value]) => `- ${key}: ${value}`).join('\n')}`;
}
