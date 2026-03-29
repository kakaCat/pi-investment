import type { ToolDefinition } from '../../infrastructure/tools/index.js';
import { Type } from '@sinclair/typebox';
import { QuantService } from './quant-service.js';
import { BacktestEngine } from './backtest-engine.js';
import { SignalGenerator } from './signal-generator.js';
import { QuantStrategy } from './types.js';

const quantService = new QuantService();
const backtestEngine = new BacktestEngine();
const signalGenerator = new SignalGenerator();

// ===== manage_quant_strategy =====
export const manageQuantStrategyTool: ToolDefinition = {
  name: 'manage_quant_strategy',
  label: '量化策略管理',
  description: '管理量化策略：创建新策略、列出所有策略、查看策略详情、删除策略、启用/禁用策略',
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal('create'),
      Type.Literal('list'),
      Type.Literal('get'),
      Type.Literal('delete'),
      Type.Literal('enable'),
      Type.Literal('disable'),
    ], { description: '操作类型' }),
    strategy_id: Type.Optional(Type.String({ description: '策略ID（get/delete/enable/disable时必需）' })),
    strategy: Type.Optional(Type.Any({ description: '策略定义（create时必需）' })),
  }),
  execute: async (_toolCallId, params: any) => {
    const { action, strategy_id, strategy } = params;

    if (action === 'create') {
      const created = await quantService.createStrategy(strategy as Omit<QuantStrategy, 'id' | 'created_at'>);
      const result = {
        success: true,
        strategy: created,
        message: `策略 ${created.name} 创建成功，ID: ${created.id}`,
      };
      return { content: [{ type: 'text' as const, text: JSON.stringify(result, null, 2) }], details: undefined };
    }

    if (action === 'list') {
      const strategies = await quantService.listStrategies();
      const result = {
        success: true,
        strategies,
        count: strategies.length,
      };
      return { content: [{ type: 'text' as const, text: JSON.stringify(result, null, 2) }], details: undefined };
    }

    if (action === 'get') {
      const strategy = await quantService.getStrategy(strategy_id);
      if (!strategy) {
        return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: '策略不存在' }) }], details: undefined };
      }
      return { content: [{ type: 'text' as const, text: JSON.stringify({ success: true, strategy }, null, 2) }], details: undefined };
    }

    if (action === 'delete') {
      const deleted = await quantService.deleteStrategy(strategy_id);
      const result = {
        success: deleted,
        message: deleted ? '策略已删除' : '策略不存在',
      };
      return { content: [{ type: 'text' as const, text: JSON.stringify(result) }], details: undefined };
    }

    if (action === 'enable' || action === 'disable') {
      const updated = await quantService.updateStrategy(strategy_id, {
        enabled: action === 'enable',
      });
      if (!updated) {
        return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: '策略不存在' }) }], details: undefined };
      }
      const result = {
        success: true,
        strategy: updated,
        message: `策略已${action === 'enable' ? '启用' : '禁用'}`,
      };
      return { content: [{ type: 'text' as const, text: JSON.stringify(result, null, 2) }], details: undefined };
    }

    return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: '未知操作' }) }], details: undefined };
  },
};

// ===== run_backtest =====
export const runBacktestTool: ToolDefinition = {
  name: 'run_backtest',
  label: '策略回测',
  description: '运行策略回测，测试策略在历史数据上的表现',
  parameters: Type.Object({
    strategy_id: Type.String({ description: '策略ID' }),
    start_date: Type.String({ description: '回测开始日期 YYYY-MM-DD' }),
    end_date: Type.String({ description: '回测结束日期 YYYY-MM-DD' }),
    initial_capital: Type.Optional(Type.Number({ description: '初始资金', default: 100000 })),
    commission: Type.Optional(Type.Number({ description: '手续费率', default: 0.0003 })),
  }),
  execute: async (_toolCallId, params: any) => {
    const { strategy_id, start_date, end_date, initial_capital = 100000, commission = 0.0003 } = params;

    const strategy = await quantService.getStrategy(strategy_id);
    if (!strategy) {
      return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: '策略不存在' }) }], details: undefined };
    }

    const result = await backtestEngine.run(strategy, {
      start_date,
      end_date,
      initial_capital,
      commission,
    });

    const output = {
      success: true,
      backtest: result,
      summary: {
        total_return: `${(result.performance.total_return * 100).toFixed(2)}%`,
        win_rate: `${(result.performance.win_rate * 100).toFixed(2)}%`,
        total_trades: result.performance.total_trades,
        profit_factor: result.performance.profit_factor.toFixed(2),
      },
    };
    return { content: [{ type: 'text' as const, text: JSON.stringify(output, null, 2) }], details: undefined };
  },
};

// ===== generate_signals =====
export const generateSignalsTool: ToolDefinition = {
  name: 'generate_signals',
  label: '生成交易信号',
  description: '生成交易信号：扫描当前市场、查看今日信号、查看历史信号',
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal('scan'),
      Type.Literal('today'),
      Type.Literal('history'),
    ], { description: 'scan=扫描生成新信号, today=查看今日信号, history=查看历史信号' }),
    strategy_id: Type.Optional(Type.String({ description: '策略ID（scan时必需）' })),
    date: Type.Optional(Type.String({ description: '日期 YYYY-MM-DD（history时可选，默认今天）' })),
  }),
  execute: async (_toolCallId, params: any) => {
    const { action, strategy_id, date } = params;

    if (action === 'scan') {
      const strategy = await quantService.getStrategy(strategy_id);
      if (!strategy) {
        return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: '策略不存在' }) }], details: undefined };
      }
      if (!strategy.enabled) {
        return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: '策略未启用' }) }], details: undefined };
      }

      const signals = await signalGenerator.scan(strategy);
      const result = {
        success: true,
        signals,
        count: signals.length,
        message: signals.length > 0 ? `发现 ${signals.length} 个交易信号` : '未发现交易信号',
      };
      return { content: [{ type: 'text' as const, text: JSON.stringify(result, null, 2) }], details: undefined };
    }

    if (action === 'today' || action === 'history') {
      const signals = await signalGenerator.getSignals(date);
      const result = {
        success: true,
        signals,
        count: signals.length,
        date: date || new Date().toISOString().split('T')[0],
      };
      return { content: [{ type: 'text' as const, text: JSON.stringify(result, null, 2) }], details: undefined };
    }

    return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: '未知操作' }) }], details: undefined };
  },
};

// 导出所有量化工具
export const quantTools: ToolDefinition[] = [
  manageQuantStrategyTool,
  runBacktestTool,
  generateSignalsTool,
];
