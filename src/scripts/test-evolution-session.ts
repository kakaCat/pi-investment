/**
 * 测试进化系统的 Session Context 机制
 */

import { getSession } from '../core/agent/agent-loop.js';
import { runWeeklyEvolution } from '../services/intelligence/evolution-service.js';

async function testEvolutionSession() {
  console.log('🧪 测试进化系统 Session Context 机制\n');

  try {
    // 1. 初始化 session 并设置上下文
    console.log('1️⃣ 初始化 Session（cron_evolution 上下文）...');
    const session = await getSession({
      type: 'cron_evolution',
      sessionId: `test-evolution-${Date.now()}`,
      metadata: { trigger: 'manual_test', jobId: 'test-evolution' }
    });
    console.log('✅ Session 初始化成功\n');

    // 2. 运行进化分析
    console.log('2️⃣ 运行进化分析...');
    const result = await runWeeklyEvolution();

    console.log('\n✅ 进化分析完成！');
    console.log('━'.repeat(60));
    console.log(`📊 报告路径: ${result.reportPath}`);
    console.log(`📈 目标收益: ${result.summary.targetReturn}% | 实际收益: ${result.summary.realizedReturn}%`);
    console.log(`🎯 胜率: ${result.summary.winRate}% | 交易次数: ${result.summary.totalTrades}`);
    console.log(`🔍 归因: ${result.summary.attribution}`);
    console.log(`💡 优化建议: ${result.summary.suggestionCount} 条`);

    if (result.summary.appliedCount > 0) {
      console.log(`✨ 已自动应用: ${result.summary.appliedCount} 条`);
    }

    if (result.summary.manualTaskCount > 0) {
      console.log(`⚠️  需人工处理: ${result.summary.manualTaskCount} 条`);
    }

    console.log('━'.repeat(60));

  } catch (error) {
    console.error('❌ 测试失败:', error instanceof Error ? error.message : String(error));
    if (error instanceof Error && error.stack) {
      console.error('\n堆栈信息:');
      console.error(error.stack);
    }
    process.exit(1);
  }
}

testEvolutionSession();
