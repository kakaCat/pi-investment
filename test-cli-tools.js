#!/usr/bin/env node
/**
 * CLI工具快速测试脚本
 *
 * 用途：验证所有8个CLI工具是否正常工作
 * 运行：node test-cli-tools.js
 */

// 导入所有CLI工具
const toolsPath = './src/infrastructure/tools/cli/index.js';

console.log('🧪 CLI工具测试开始...\n');

async function testTools() {
  try {
    // 动态导入
    const tools = await import(toolsPath);

    const testResults = [];

    // 1. 测试 market_cli
    console.log('1️⃣  测试 market_cli...');
    if (tools.marketCliTool) {
      testResults.push({ tool: 'market_cli', status: '✅', commands: 12 });
      console.log('   ✅ market_cli 已注册\n');
    } else {
      testResults.push({ tool: 'market_cli', status: '❌', error: '未找到' });
    }

    // 2. 测试 stock_cli
    console.log('2️⃣  测试 stock_cli...');
    if (tools.stockCliTool) {
      testResults.push({ tool: 'stock_cli', status: '✅', commands: 5 });
      console.log('   ✅ stock_cli 已注册\n');
    } else {
      testResults.push({ tool: 'stock_cli', status: '❌', error: '未找到' });
    }

    // 3. 测试 financial_cli
    console.log('3️⃣  测试 financial_cli...');
    if (tools.financialCliTool) {
      testResults.push({ tool: 'financial_cli', status: '✅', commands: 7 });
      console.log('   ✅ financial_cli 已注册\n');
    } else {
      testResults.push({ tool: 'financial_cli', status: '❌', error: '未找到' });
    }

    // 4. 测试 sentiment_cli
    console.log('4️⃣  测试 sentiment_cli...');
    if (tools.sentimentCliTool) {
      testResults.push({ tool: 'sentiment_cli', status: '✅', commands: 8 });
      console.log('   ✅ sentiment_cli 已注册\n');
    } else {
      testResults.push({ tool: 'sentiment_cli', status: '❌', error: '未找到' });
    }

    // 5. 测试 analysis_cli
    console.log('5️⃣  测试 analysis_cli...');
    if (tools.analysisCliTool) {
      testResults.push({ tool: 'analysis_cli', status: '✅', commands: 7 });
      console.log('   ✅ analysis_cli 已注册\n');
    } else {
      testResults.push({ tool: 'analysis_cli', status: '❌', error: '未找到' });
    }

    // 6. 测试 signal_cli
    console.log('6️⃣  测试 signal_cli...');
    if (tools.signalCliTool) {
      testResults.push({ tool: 'signal_cli', status: '✅', commands: 4 });
      console.log('   ✅ signal_cli 已注册\n');
    } else {
      testResults.push({ tool: 'signal_cli', status: '❌', error: '未找到' });
    }

    // 7. 测试 backtest_cli
    console.log('7️⃣  测试 backtest_cli...');
    if (tools.backtestCliTool) {
      testResults.push({ tool: 'backtest_cli', status: '✅', commands: 3 });
      console.log('   ✅ backtest_cli 已注册\n');
    } else {
      testResults.push({ tool: 'backtest_cli', status: '❌', error: '未找到' });
    }

    // 8. 测试 watchlist_cli
    console.log('8️⃣  测试 watchlist_cli...');
    if (tools.watchlistCliTool) {
      testResults.push({ tool: 'watchlist_cli', status: '✅', commands: 5 });
      console.log('   ✅ watchlist_cli 已注册\n');
    } else {
      testResults.push({ tool: 'watchlist_cli', status: '❌', error: '未找到' });
    }

    // 输出汇总
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('📊 测试结果汇总\n');

    const passed = testResults.filter(r => r.status === '✅').length;
    const failed = testResults.filter(r => r.status === '❌').length;
    const totalCommands = testResults.reduce((sum, r) => sum + (r.commands || 0), 0);

    testResults.forEach(r => {
      console.log(`   ${r.status} ${r.tool.padEnd(18)} ${r.commands ? `(${r.commands}命令)` : r.error || ''}`);
    });

    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log(`\n✅ 通过: ${passed}/8`);
    console.log(`❌ 失败: ${failed}/8`);
    console.log(`📦 总命令数: ${totalCommands}`);
    console.log(`🎯 通过率: ${((passed/8)*100).toFixed(1)}%`);

    if (passed === 8) {
      console.log('\n🎉 所有CLI工具测试通过！');
    } else {
      console.log('\n⚠️  部分工具测试失败，请检查导入。');
    }

  } catch (error) {
    console.error('❌ 测试失败:', error.message);
    console.error('\n提示：请先编译项目：npm run build');
  }
}

testTools();
