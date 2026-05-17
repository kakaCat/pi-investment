/**
 * Quant Strategy Tools - 量化策略管理工具集
 *
 * 提供策略查询和性能统计工具
 */

import { Type } from '@sinclair/typebox';
import type { ToolDefinition } from "./index.js";
import { QuantService } from '../../services/quant/quant-service.js';
import { PerformanceAnalyzer } from '../../services/quant/performance-analyzer.js';

// 初始化服务
const quantService = new QuantService();
const performanceAnalyzer = new PerformanceAnalyzer('.pi-invest/quant/signals');

/**
 * 1. list_quant_strategies - 列出量化策略
 */
export const listQuantStrategiesTool: ToolDefinition = {
  name: 'list_quant_strategies',
  label: '列出量化策略',
  description: `查看所有可用的量化策略。

返回内容：
- 策略ID和名称
- 启用状态
- 创建时间
- 策略描述

适用场景：
- 查看可用策略
- 选择回测策略
- 了解策略配置`,

  parameters: Type.Object({}),

  execute: async (_toolCallId: string, _params: any) => {
    try {
      const strategies = await quantService.listStrategies();

      if (strategies.length === 0) {
        return {
          content: [{ type: "text" as const, text: '暂无量化策略' }],
          details: undefined
        };
      }

      const summary = `
量化策略列表 (共${strategies.length}个)
=====================================
${strategies.map((s, i) => {
  const status = s.enabled ? '✓ 启用' : '✗ 禁用';
  return `${i + 1}. ${s.name} (${s.id})
   状态: ${status}
   描述: ${s.description || '无描述'}
   创建时间: ${s.created_at}`;
}).join('\n\n')}

使用方法:
- 回测策略: backtest_strategy(strategy_id="${strategies[0].id}", ...)
- 查看表现: get_strategy_performance(strategy_id="${strategies[0].id}")
`.trim();

      return {
        content: [{ type: "text" as const, text: summary }],
        details: strategies.map(s => ({
          id: s.id,
          name: s.name,
          enabled: s.enabled,
          description: s.description,
          created_at: s.created_at
        }))
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `获取策略列表失败: ${msg}` }],
        details: undefined
      };
    }
  }
};

/**
 * 2. get_strategy_performance - 获取策略表现
 */
export const getStrategyPerformanceTool: ToolDefinition = {
  name: 'get_strategy_performance',
  label: '获取策略表现',
  description: `查看量化策略的历史表现统计。

统计指标：
- 总信号数（买入/卖出）
- 胜率
- 平均收益率
- 最大盈利/亏损
- 信号分布

适用场景：
- 评估策略效果
- 选择优质策略
- 优化策略参数`,

  parameters: Type.Object({
    strategy_id: Type.String({
      description: '策略ID'
    }),
    days: Type.Optional(Type.Number({
      description: '统计天数（可选），默认统计全部历史'
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { strategy_id, days } = params;

      // 获取策略信息
      const strategy = await quantService.getStrategy(strategy_id);
      if (!strategy) {
        return {
          content: [{ type: "text" as const, text: `策略 ${strategy_id} 不存在` }],
          details: undefined
        };
      }

      // 分析策略表现
      const metrics = await performanceAnalyzer.analyzeStrategy(strategy_id, days);

      const summary = `
策略表现统计 - ${strategy.name}
=====================================
统计周期: ${days ? `最近${days}天` : '全部历史'}

信号统计:
- 总信号数: ${metrics.total_signals}
- 买入信号: ${metrics.buy_signals}
- 卖出信号: ${metrics.sell_signals}

收益统计:
- 胜率: ${(metrics.win_rate * 100).toFixed(2)}%
- 平均收益: ${metrics.avg_return.toFixed(2)}%
- 最大盈利: ${metrics.max_gain.toFixed(2)}%
- 最大亏损: ${metrics.max_loss.toFixed(2)}%

信号质量:
- 平均置信度: ${(metrics.avg_confidence * 100).toFixed(0)}%
- 有效信号比例: ${((metrics.winning_signals / metrics.total_signals) * 100).toFixed(0)}%

策略评价: ${metrics.win_rate >= 0.6 ? '表现优秀' : metrics.win_rate >= 0.5 ? '表现良好' : '需要优化'}
`.trim();

      return {
        content: [{ type: "text" as const, text: summary }],
        details: metrics
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `获取策略表现失败: ${msg}` }],
        details: undefined
      };
    }
  }
};

// 导出工具数组
export const quantStrategyTools = [
  listQuantStrategiesTool,
  getStrategyPerformanceTool
];
