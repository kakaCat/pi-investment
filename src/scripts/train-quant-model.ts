/**
 * 训练量化信号模型
 *
 * 用法：
 *   npx tsx src/scripts/train-quant-model.ts [days] [min_samples]
 *
 * 参数：
 *   days: 使用最近多少天的历史信号（默认30天）
 *   min_samples: 最小样本数要求（默认50）
 */

import { callPythonResilient } from '../infrastructure/tools/shared/python-caller-resilient-adapter.js';

const days = parseInt(process.argv[2]) || 30;
const minSamples = parseInt(process.argv[3]) || 50;

async function trainModel() {
  console.log('=== 量化信号模型训练 ===\n');
  console.log(`📚 训练参数:`);
  console.log(`   - 历史天数: ${days} 天`);
  console.log(`   - 最小样本: ${minSamples} 条`);
  console.log();

  console.log('🔄 开始训练...');

  try {
    const result = await callPythonResilient(
      'train_signal_model',
      { days, min_samples: minSamples },
      { timeout: 60000 }
    );

    if (result.error) {
      console.error('❌ 训练失败:', result.error);

      if (result.samples !== undefined) {
        console.log(`\n📊 当前样本数: ${result.samples}`);
        console.log(`📊 需要样本数: ${result.required}`);
        console.log('\n💡 建议:');
        console.log('   1. 降低 min_samples 参数');
        console.log('   2. 增加 days 参数以获取更多历史数据');
        console.log('   3. 运行信号生成以积累更多历史信号');
      }

      return;
    }

    console.log('\n✅ 训练完成！\n');
    console.log('📊 训练数据:');
    console.log(`   - 总样本数: ${result.samples}`);
    console.log(`   - 正样本: ${result.positive_samples} (${((result.positive_samples / result.samples) * 100).toFixed(1)}%)`);
    console.log(`   - 负样本: ${result.negative_samples} (${((result.negative_samples / result.samples) * 100).toFixed(1)}%)`);

    console.log('\n📈 模型性能:');
    console.log(`   - 准确率: ${(result.accuracy * 100).toFixed(2)}%`);

    if (result.accuracy >= 0.6) {
      console.log('   ✅ 准确率良好 (≥60%)');
    } else if (result.accuracy >= 0.5) {
      console.log('   ⚠️  准确率一般 (50%-60%)');
    } else {
      console.log('   ❌ 准确率较低 (<50%)');
    }

    console.log('\n💾 模型文件:');
    console.log(`   ${result.model_path}`);

    if (result.feature_importance && result.feature_importance.length > 0) {
      console.log('\n🎯 特征重要性 (Top 5):');
      const featureNames = [
        'RSI', 'MACD', 'MACD信号', 'MACD柱',
        'MA5', 'MA10', 'MA20', 'MA60',
        '布林上轨', '布林中轨', '布林下轨',
        '成交量', '成交量MA5', '成交量MA10',
        '价格动量', '成交量动量', '置信度'
      ];

      const topFeatures = result.feature_importance
        .map((imp: number, idx: number) => ({ name: featureNames[idx] || `特征${idx+1}`, importance: imp }))
        .sort((a: any, b: any) => b.importance - a.importance)
        .slice(0, 5);

      topFeatures.forEach((f: any, i: number) => {
        console.log(`   ${i + 1}. ${f.name}: ${(f.importance * 100).toFixed(2)}%`);
      });
    }

    console.log('\n💡 下一步:');
    console.log('   - 生成可视化图表: npx tsx src/scripts/generate-quant-charts.ts importance');
    console.log('   - 使用模型预测: 在信号生成时会自动使用训练好的模型');

  } catch (error) {
    console.error('❌ 训练异常:', error);
  }
}

trainModel().catch(console.error);
