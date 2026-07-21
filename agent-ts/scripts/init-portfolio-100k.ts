#!/usr/bin/env tsx
/**
 * 初始化虚拟仓 - 10万元
 */
import { portfolioStatusTool } from '../src/infrastructure/tools/portfolio/portfolio-status-tool.js';

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('💰 初始化虚拟仓 - 10万元');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

async function main() {
  try {
    // 1. 检查当前状态
    console.log('📊 步骤1: 检查当前虚拟仓状态...');
    const statusResult = await portfolioStatusTool.execute('check-1', {});
    const statusData = JSON.parse(statusResult.content[0].text);

    console.log(`   可用资金: ¥${statusData.cash.toFixed(2)}`);
    console.log(`   持仓数量: ${statusData.holdings_count}只`);
    console.log(`   总资产: ¥${statusData.total_assets.toFixed(2)}\n`);

    if (statusData.cash > 0) {
      console.log('✅ 虚拟仓已初始化！');
      console.log(`   当前资金: ¥${statusData.cash.toFixed(2)}\n`);
      return;
    }

    // 2. 初始化虚拟仓
    console.log('💡 步骤2: 初始化虚拟仓（10万元）...');
    console.log('   方式: 直接调用后端API\n');

    const initResponse = await fetch('http://127.0.0.1:5001/api/portfolio/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        initial_cash: 100000,
        reset_holdings: true
      })
    });

    const initResult = await initResponse.json();

    if (initResult.success) {
      console.log('✅ 初始化成功！');
      console.log(`   初始资金: ¥${initResult.data.cash.toFixed(2)}\n`);
    } else {
      console.log(`⚠️  初始化失败: ${initResult.error || '未知错误'}`);
      console.log('   尝试使用交易接口模拟初始化...\n');

      // 备用方案：创建一个初始记录
      console.log('💡 使用数据库直接初始化...');
      console.log('   需要: PostgreSQL直接写入或通过quantsys-v2内部接口\n');
    }

    // 3. 再次检查状态
    console.log('📊 步骤3: 验证初始化结果...');
    const finalResult = await portfolioStatusTool.execute('check-2', {});
    const finalData = JSON.parse(finalResult.content[0].text);

    console.log(`   可用资金: ¥${finalData.cash.toFixed(2)}`);
    console.log(`   总资产: ¥${finalData.total_assets.toFixed(2)}\n`);

    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ 虚拟仓初始化流程完成');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    console.log('\n💡 下一步:');
    console.log('   • 明天 09:00 早盘分析任务会自动运行');
    console.log('   • Agent会扫描股票池寻找交易机会');
    console.log('   • 如发现高质量信号（≥80分），会执行买入');
    console.log('   • 所有操作都在虚拟仓中，不涉及真实资金\n');

  } catch (error) {
    console.error('\n❌ 初始化失败:', error);
    process.exit(1);
  }
}

main();
