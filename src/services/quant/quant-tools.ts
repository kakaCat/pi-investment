import type { ToolDefinition } from '../../infrastructure/tools/index.js';
import { Type } from '@sinclair/typebox';
import { QuantService } from './quant-service.js';
import { BacktestEngine } from './backtest-engine.js';
import { SignalGenerator } from './signal-generator.js';
import { FactorLibrary } from './factor-library.js';
import { QuantStrategy } from './types.js';
import { TS_FUNCTIONS } from '../../infrastructure/akshare-ts/index.js';
import { isHkSymbol } from '../../infrastructure/data-sources/sina.js';

const quantService = new QuantService();
const backtestEngine = new BacktestEngine();
const signalGenerator = new SignalGenerator();
const factorLibrary = new FactorLibrary();

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

// ===== score_stock =====
export const scoreStockTool: ToolDefinition = {
  name: 'score_stock',
  label: '因子评分',
  description: '对单只股票进行多因子评分（估值+技术+动量），自动拉取实时数据，返回 A-F 等级和各因子得分',
  parameters: Type.Object({
    symbol: Type.String({ description: '股票代码，如 600519 或 00700' }),
    weights: Type.Optional(Type.Object({
      pe: Type.Optional(Type.Number({ description: 'PE估值因子权重，默认0.20' })),
      pb: Type.Optional(Type.Number({ description: 'PB估值因子权重，默认0.10' })),
      rsi: Type.Optional(Type.Number({ description: 'RSI技术因子权重，默认0.15' })),
      trend: Type.Optional(Type.Number({ description: '趋势因子权重，默认0.20' })),
      macd: Type.Optional(Type.Number({ description: 'MACD因子权重，默认0.10' })),
      momentum: Type.Optional(Type.Number({ description: '动量因子权重，默认0.25' })),
    }, { description: '自定义因子权重（可选，未指定的使用默认值）' })),
  }),
  execute: async (_toolCallId, params: any) => {
    const { symbol, weights } = params;

    // HK 股票暂不支持（缺少 PE 分位、技术指标等数据源）
    if (isHkSymbol(symbol)) {
      return {
        content: [{ type: 'text' as const, text: `港股 ${symbol} 暂不支持因子评分（缺少 PE 分位数、历史技术指标等数据源）` }],
        details: undefined,
      };
    }

    // 并行拉取实时价格 + 技术指标 + PE分位 + 近期历史（算动量）
    const [priceJson, techJson, peJson, histJson] = await Promise.all([
      Promise.resolve(TS_FUNCTIONS['get_stock_realtime_price']({ symbol })).catch(() => '{}'),
      Promise.resolve(TS_FUNCTIONS['calculate_technical_indicators']({ symbol, indicators: ['ma', 'rsi', 'macd'] })).catch(() => '{}'),
      Promise.resolve(TS_FUNCTIONS['get_pe_percentile']({ symbol })).catch(() => '{}'),
      Promise.resolve(TS_FUNCTIONS['get_stock_history']({ symbol, period: 'daily', limit: 25 })).catch(() => '{}'),
    ]);

    const price = JSON.parse(priceJson);
    const tech = JSON.parse(techJson);
    const pe = JSON.parse(peJson);
    const hist = JSON.parse(histJson);

    // 计算20日涨跌幅作为动量因子（比今日涨跌更有意义）
    let change20: number | undefined;
    const rows: any[] = hist.data || [];
    if (rows.length >= 21) {
      const cur = rows[rows.length - 1].close;
      const prev20 = rows[rows.length - 21].close;
      change20 = ((cur - prev20) / prev20) * 100;
    }

    // Sina 实时行情字段：price（非 current），pe_dynamic（非 pe），pb 为 0 时视为无效
    const curPrice = price.price ?? price.current;
    const peVal = (pe.current_pe || price.pe_dynamic) || undefined;   // 0 视为无效
    const pbVal = price.pb > 0 ? price.pb : undefined;

    const data = {
      pe: peVal,
      pe_percentile: pe.pe_percentile ?? undefined,
      pb: pbVal,
      rsi: tech.rsi ?? undefined,
      ma5: tech.ma5 ?? undefined,
      ma20: tech.ma20 ?? undefined,
      ma60: tech.ma60 ?? undefined,
      macd_histogram: tech.macd_histogram ?? undefined,
      change_pct: change20,
    };

    const result = factorLibrary.calculate(symbol, data, weights);

    // 格式化输出
    const factorLines = result.factors.map(f =>
      `  ${f.name.padEnd(10)} ${f.score.toString().padStart(3)}分  权重${(f.weight * 100).toFixed(0)}%  ${f.reason}`
    ).join('\n');

    const summary = [
      `股票: ${price.name || symbol} (${symbol})`,
      `综合评分: ${result.total_score} / 100  等级: ${result.grade}`,
      `当前价格: ${curPrice ?? '-'}  今日涨跌: ${price.change_pct != null ? price.change_pct.toFixed(2) + '%' : '-'}  20日涨跌: ${change20 != null ? change20.toFixed(2) + '%' : '-'}`,
      '',
      '因子明细:',
      factorLines || '  (数据不足，无法评分)',
    ].join('\n');

    return {
      content: [{ type: 'text' as const, text: summary }],
      details: result,
    };
  },
};

// ===== train_signal_model =====
export const trainSignalModelTool: ToolDefinition = {
  name: 'train_signal_model',
  label: '训练信号模型',
  description: '训练或查看 XGBoost 信号置信度模型状态',
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal('train'),
      Type.Literal('status'),
    ], { description: 'train=训练模型, status=查看模型状态' }),
  }),
  execute: async (_toolCallId, params: any) => {
    const { action } = params;

    if (action === 'train') {
      // 调用 Python 训练脚本
      const { execFile } = await import('child_process');
      const { promisify } = await import('util');
      const execFileAsync = promisify(execFile);

      try {
        const { stdout } = await execFileAsync('python3', ['python/ml/signal_trainer.py'], { timeout: 120000 });
        const result = JSON.parse(stdout.trim());
        return { content: [{ type: 'text' as const, text: JSON.stringify(result, null, 2) }], details: undefined };
      } catch (err: any) {
        return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: err.message }) }], details: undefined };
      }
    }

    if (action === 'status') {
      const fs = await import('fs/promises');
      const modelPath = '.pi-invest/quant/models/signal_confidence.pkl';
      const signalsDir = '.pi-invest/quant/signals';

      try {
        const modelExists = await fs.access(modelPath).then(() => true).catch(() => false);
        const signalFiles = await fs.readdir(signalsDir).catch(() => []);
        const signalCount = signalFiles.filter(f => f.endsWith('.json')).length;

        const status = {
          model_exists: modelExists,
          model_path: modelPath,
          signal_files: signalCount,
          min_samples_required: 50,
          ready_to_train: signalCount >= 50,
        };

        return { content: [{ type: 'text' as const, text: JSON.stringify(status, null, 2) }], details: undefined };
      } catch (err: any) {
        return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: err.message }) }], details: undefined };
      }
    }

    return { content: [{ type: 'text' as const, text: JSON.stringify({ success: false, error: '未知操作' }) }], details: undefined };
  },
};

// 导出所有量化工具
export const quantTools: ToolDefinition[] = [
  manageQuantStrategyTool,
  runBacktestTool,
  generateSignalsTool,
  scoreStockTool,
  trainSignalModelTool,
];
