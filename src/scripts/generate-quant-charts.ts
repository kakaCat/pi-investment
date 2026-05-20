/**
 * 生成量化系统可视化图表
 *
 * 用法：
 *   npx tsx src/scripts/generate-quant-charts.ts [chart-type]
 *
 * chart-type:
 *   - accuracy: 模型准确率趋势图
 *   - equity: 回测权益曲线图
 *   - comparison: 策略胜率对比图
 *   - importance: 特征重要性图
 *   - all: 生成所有图表（默认）
 */

import { callPythonResilient } from '../infrastructure/tools/shared/python-caller-resilient-adapter.js';
import { QuantService } from '../services/quant/quant-service.js';
import { BacktestEngine } from '../services/quant/backtest-engine.js';
import { PerformanceAnalyzer } from '../services/quant/performance-analyzer.js';

const chartType = process.argv[2] || 'all';

type PythonResult = Record<string, any>;

function parsePythonResult(raw: string): PythonResult {
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : { value: parsed };
  } catch {
    return { error: raw };
  }
}

async function generateAccuracyTrend() {
  console.log('\n📊 生成模型准确率趋势图...');

  try {
    const result = parsePythonResult(await callPythonResilient(
      'plot_model_accuracy_trend',
      { days: 90 }
    ));

    if (result.error) {
      console.error('❌ 生成失败:', result.error);
      if (result.suggestion) {
        console.log('💡', result.suggestion);
      }
      return;
    }

    console.log('✅ 图表已生成:', result.chart_path);
    console.log('📈 统计信息:');
    console.log(`   - 最新准确率: ${result.stats.latest_accuracy}%`);
    console.log(`   - 平均准确率: ${result.stats.avg_accuracy}%`);
    console.log(`   - 最高准确率: ${result.stats.max_accuracy}%`);
    console.log(`   - 训练次数: ${result.stats.training_count}`);
  } catch (error) {
    console.error('❌ 异常:', error);
  }
}

async function generateEquityCurve() {
  console.log('\n📊 生成回测权益曲线图...');

  try {
    // 获取一个策略进行回测
    const quantService = new QuantService();
    const strategies = await quantService.listStrategies();

    if (strategies.length === 0) {
      console.log('⚠️  没有可用的策略，跳过权益曲线图');
      return;
    }

    const strategy = strategies[0];
    console.log(`   使用策略: ${strategy.name}`);

    // 运行回测
    const engine = new BacktestEngine();
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    console.log(`   回测期间: ${startDate} 至 ${endDate}`);

    const backtest = await engine.runBacktest(
      strategy,
      startDate,
      endDate,
      ['600036', '601088', '000425'], // 示例股票
      100000 // 初始资金
    );

    // 生成图表
    const result = parsePythonResult(await callPythonResilient(
      'plot_equity_curve',
      { backtest_result: backtest }
    ));

    if (result.error) {
      console.error('❌ 生成失败:', result.error);
      return;
    }

    console.log('✅ 图表已生成:', result.chart_path);
    console.log('📈 统计信息:');
    console.log(`   - 初始资金: ${result.stats.initial_capital}`);
    console.log(`   - 最终资金: ${result.stats.final_capital}`);
    console.log(`   - 总收益率: ${result.stats.total_return}%`);
    console.log(`   - 最大回撤: ${result.stats.max_drawdown}%`);
  } catch (error) {
    console.error('❌ 异常:', error);
  }
}

async function generateStrategyComparison() {
  console.log('\n📊 生成策略胜率对比图...');

  try {
    const quantService = new QuantService();
    const strategies = await quantService.listStrategies();

    if (strategies.length === 0) {
      console.log('⚠️  没有可用的策略，跳过对比图');
      return;
    }

    console.log(`   分析 ${strategies.length} 个策略...`);

    // 获取每个策略的性能
    const analyzer = new PerformanceAnalyzer();
    const performances = [];

    for (const strategy of strategies.slice(0, 10)) { // 最多10个策略
      try {
        const metrics = await analyzer.analyzeStrategy(
          strategy.id,
          strategy.name,
          30
        );
        performances.push(metrics);
      } catch (e) {
        console.log(`   ⚠️  策略 ${strategy.name} 分析失败`);
      }
    }

    if (performances.length === 0) {
      console.log('⚠️  没有策略性能数据，跳过对比图');
      return;
    }

    // 生成图表
    const result = parsePythonResult(await callPythonResilient(
      'plot_strategy_comparison',
      { strategies_performance: performances }
    ));

    if (result.error) {
      console.error('❌ 生成失败:', result.error);
      return;
    }

    console.log('✅ 图表已生成:', result.chart_path);
    console.log('📈 统计信息:');
    console.log(`   - 最佳策略: ${result.stats.best_strategy}`);
    console.log(`   - 平均胜率: ${result.stats.avg_win_rate}%`);
    console.log(`   - 策略总数: ${result.stats.total_strategies}`);
  } catch (error) {
    console.error('❌ 异常:', error);
  }
}

async function generateFeatureImportance() {
  console.log('\n📊 生成特征重要性图...');

  try {
    const result = parsePythonResult(await callPythonResilient(
      'plot_feature_importance',
      {}
    ));

    if (result.error) {
      console.error('❌ 生成失败:', result.error);
      if (result.error.includes('Model not found')) {
        console.log('💡 请先训练模型: npx tsx src/scripts/train-quant-model.ts');
      }
      return;
    }

    console.log('✅ 图表已生成:', result.chart_path);
    console.log('📈 统计信息:');
    console.log(`   - 最重要特征: ${result.stats.top_feature}`);
    console.log(`   - 重要性: ${result.stats.top_importance}%`);
    console.log(`   - 特征总数: ${result.stats.total_features}`);
  } catch (error) {
    console.error('❌ 异常:', error);
  }
}

async function main() {
  console.log('=== 量化系统可视化图表生成器 ===\n');

  switch (chartType) {
    case 'accuracy':
      await generateAccuracyTrend();
      break;
    case 'equity':
      await generateEquityCurve();
      break;
    case 'comparison':
      await generateStrategyComparison();
      break;
    case 'importance':
      await generateFeatureImportance();
      break;
    case 'all':
      await generateAccuracyTrend();
      await generateEquityCurve();
      await generateStrategyComparison();
      await generateFeatureImportance();
      break;
    default:
      console.error('❌ 未知的图表类型:', chartType);
      console.log('\n可用类型: accuracy, equity, comparison, importance, all');
      process.exit(1);
  }

  console.log('\n✅ 完成！图表保存在 .pi-invest/quant/charts/ 目录');
}

main().catch(console.error);
