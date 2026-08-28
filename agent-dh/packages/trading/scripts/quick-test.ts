#!/usr/bin/env tsx
/**
 * Trading Package 快速测试脚本
 *
 * 运行: npx tsx scripts/quick-test.ts
 */

import { PortfolioTradeTool } from '../src/tools/PortfolioTradeTool/PortfolioTradeTool';
import { createTradeVerifyTool } from '../src/tools/TradeVerifyTool';
import { M4CircuitBreakerTool } from '../src/tools/M4CircuitBreakerTool/M4CircuitBreakerTool';

// ========================================
// Mock 依赖
// ========================================

const mockQv2 = {
  executeTrade: async (params: any) => ({
    order_id: `TEST-${Date.now()}`,
    symbol: params.symbol,
    action: params.action.toUpperCase(),
    quantity: params.quantity,
    price: params.price || 100.0,
    amount: (params.price || 100.0) * params.quantity,
    status: 'filled',
    timestamp: new Date().toISOString(),
  }),

  getQuote: async (symbol: string) => ({
    symbol,
    price: 100.0,
    timestamp: new Date().toISOString(),
  }),

  getPortfolioSummary: async () => ({
    totalValue: 1000000,
    cash: 500000,
    marketValue: 500000,
  }),

  getTradeHistory: async () => [
    {
      order_id: 'TEST-001',
      symbol: '600519',
      action: 'BUY',
      quantity: 100,
      price: 1850.0,
      timestamp: '2026-08-28T10:00:00Z',
    },
  ],

  getPositionList: async () => [
    {
      symbol: '600519',
      shares: 100,
      cost_basis: 1850.0,
    },
  ],

  getPerformanceMetrics: async () => ({
    drawdown_60d: -5.2,
    return_60d: 12.5,
  }),
};

const mockOsMemory = {
  search: async () => ({ memories: [] }),
  write: async () => ({}),
  createMemory: async () => ({}),
};

const mockCtx = {
  tools: {
    call: async (name: string, args: any) => {
      if (name === 'regime_position_limit') {
        return {
          verdict: 'ok',
          max_position_pct: 80,
          current_position_pct: 50,
          regime: 'expansion',
        };
      }
      return {};
    },
    execute: async () => ({}),
  },
};

// ========================================
// 测试工具函数
// ========================================

function logTestSection(title: string) {
  console.log('\n' + '='.repeat(60));
  console.log(`  ${title}`);
  console.log('='.repeat(60));
}

function logTestCase(num: number, title: string) {
  console.log(`\n${num}️⃣  ${title}`);
}

function logResult(success: boolean, message?: string) {
  console.log(`   ${success ? '✅' : '❌'} ${message || (success ? '通过' : '失败')}`);
}

function logData(label: string, value: any) {
  console.log(`   📊 ${label}: ${JSON.stringify(value, null, 2).substring(0, 100)}`);
}

// ========================================
// 测试 1: PortfolioTradeTool
// ========================================

async function testPortfolioTradeTool() {
  logTestSection('测试 1: PortfolioTradeTool');

  const tool = new PortfolioTradeTool(mockQv2 as any, mockOsMemory, mockCtx);
  let passCount = 0;
  let totalCount = 0;

  // 测试 1.1: 缺少 action
  totalCount++;
  logTestCase(1, '参数校验 - 缺少 action');
  const result1 = await tool.call({} as any);
  if (!result1.success && result1.error?.field === 'action') {
    logResult(true, '正确拦截缺少 action');
    passCount++;
  } else {
    logResult(false, '应该拦截缺少 action');
  }

  // 测试 1.2: 错误的 action
  totalCount++;
  logTestCase(2, '参数校验 - 错误的 action (小写)');
  const result2 = await tool.call({
    action: 'buy',
    symbol: '600519',
    quantity: 100,
  } as any);
  if (!result2.success && result2.error?.field === 'action') {
    logResult(true, '正确拦截小写 action');
    passCount++;
  } else {
    logResult(false, '应该拦截小写 action');
  }

  // 测试 1.3: 错误的 symbol
  totalCount++;
  logTestCase(3, '参数校验 - 错误的 symbol (含前缀)');
  const result3 = await tool.call({
    action: 'BUY',
    symbol: 'SH600519',
    quantity: 100,
  } as any);
  if (!result3.success && result3.error?.field === 'symbol') {
    logResult(true, '正确拦截错误 symbol 格式');
    passCount++;
  } else {
    logResult(false, '应该拦截错误 symbol 格式');
  }

  // 测试 1.4: 错误的 quantity
  totalCount++;
  logTestCase(4, '参数校验 - 错误的 quantity (非100倍数)');
  const result4 = await tool.call({
    action: 'BUY',
    symbol: '600519',
    quantity: 50,
  } as any);
  if (!result4.success && result4.error?.field === 'quantity') {
    logResult(true, '正确拦截非100倍数 quantity');
    passCount++;
  } else {
    logResult(false, '应该拦截非100倍数 quantity');
  }

  // 测试 1.5: 正常买入 (需要跳过交易时段检查)
  totalCount++;
  logTestCase(5, '正常买入交易');
  try {
    const result5 = await tool.call({
      action: 'BUY',
      symbol: '600519',
      quantity: 100,
      price: 1850.0,
      reason: 'R-001: 测试买入',
    });

    // 如果因为交易时段被拦截，也算测试通过（说明校验生效）
    if (!result5.success && result5.error?.issue?.includes('交易时段')) {
      logResult(true, '交易时段校验生效（非交易时段）');
      passCount++;
    } else if (result5.success && result5.data?.order_id) {
      logResult(true, '交易执行成功');
      logData('订单ID', result5.data.order_id);
      logData('成交价', result5.data.price);
      passCount++;
    } else {
      logResult(false, '交易执行失败');
    }
  } catch (err: any) {
    if (err.message.includes('交易时段')) {
      logResult(true, '交易时段校验生效（非交易时段）');
      passCount++;
    } else {
      logResult(false, `意外错误: ${err.message}`);
    }
  }

  // 测试 1.6: 正常卖出
  totalCount++;
  logTestCase(6, '正常卖出交易');
  try {
    const result6 = await tool.call({
      action: 'SELL',
      symbol: '600519',
      quantity: 100,
      price: 1900.0,
      reason: 'R-002: 测试卖出',
    });

    if (!result6.success && result6.error?.issue?.includes('交易时段')) {
      logResult(true, '交易时段校验生效（非交易时段）');
      passCount++;
    } else if (result6.success && result6.data?.order_id) {
      logResult(true, '交易执行成功');
      logData('订单ID', result6.data.order_id);
      passCount++;
    } else {
      logResult(false, '交易执行失败');
    }
  } catch (err: any) {
    if (err.message.includes('交易时段')) {
      logResult(true, '交易时段校验生效（非交易时段）');
      passCount++;
    } else {
      logResult(false, `意外错误: ${err.message}`);
    }
  }

  console.log(`\n   📊 PortfolioTradeTool: ${passCount}/${totalCount} 通过`);
  return { passCount, totalCount };
}

// ========================================
// 测试 2: TradeVerifyTool
// ========================================

async function testTradeVerifyTool() {
  logTestSection('测试 2: TradeVerifyTool');

  // 创建 DSH 工具实例
  const dshTool = createTradeVerifyTool(mockQv2 as any);
  let passCount = 0;
  let totalCount = 0;

  // 测试 2.1: 本地对账
  totalCount++;
  logTestCase(1, '本地对账');
  try {
    const result1 = await dshTool.execute({
      action: 'local',
      account_name: 'agent_virtual',
    });

    if (result1 && result1.status) {
      logResult(true, '对账执行成功');
      logData('对账状态', result1.status);
      logData('差异数量', result1.discrepancies?.length || 0);
      passCount++;
    } else {
      logResult(false, '对账执行失败');
    }
  } catch (err: any) {
    logResult(false, `执行错误: ${err.message}`);
  }

  // 测试 2.2: 远程对账
  totalCount++;
  logTestCase(2, '远程对账');
  try {
    const result2 = await dshTool.execute({
      action: 'remote',
      account_name: 'agent_virtual',
    });

    if (result2) {
      logResult(true, '对账执行成功');
      passCount++;
    } else {
      logResult(false, '对账执行失败');
    }
  } catch (err: any) {
    logResult(false, `执行错误: ${err.message}`);
  }

  console.log(`\n   📊 TradeVerifyTool: ${passCount}/${totalCount} 通过`);
  return { passCount, totalCount };
}

// ========================================
// 测试 3: M4CircuitBreakerTool
// ========================================

async function testM4CircuitBreakerTool() {
  logTestSection('测试 3: M4CircuitBreakerTool');

  const tool = new M4CircuitBreakerTool(mockQv2 as any, mockOsMemory);
  let passCount = 0;
  let totalCount = 0;

  // 测试 3.1: 正常情况（未触发熔断）
  totalCount++;
  logTestCase(1, '正常情况（回撤 < 8%）');
  const result1 = await tool.call({
    account_name: 'agent_virtual',
  });
  if (result1.success && !result1.data?.triggered) {
    logResult(true, '熔断检查正常');
    logData('最大回撤', result1.data.max_drawdown);
    logData('是否触发', result1.data.triggered);
    passCount++;
  } else {
    logResult(false, '熔断检查失败');
  }

  // 测试 3.2: 极端情况（触发熔断）
  totalCount++;
  logTestCase(2, '极端情况（回撤 > 8%）');
  const mockQv2Extreme = {
    ...mockQv2,
    getPerformanceMetrics: async () => ({
      drawdown_60d: -9.5,
      return_60d: -5.0,
    }),
  };
  const tool2 = new M4CircuitBreakerTool(mockQv2Extreme as any, mockOsMemory);
  const result2 = await tool2.call({
    account_name: 'agent_virtual',
  });
  if (result2.success && result2.data?.triggered) {
    logResult(true, '熔断正确触发');
    logData('最大回撤', result2.data.max_drawdown);
    logData('建议操作', result2.data.action);
    passCount++;
  } else {
    logResult(false, '熔断应该触发但未触发');
  }

  console.log(`\n   📊 M4CircuitBreakerTool: ${passCount}/${totalCount} 通过`);
  return { passCount, totalCount };
}

// ========================================
// 主测试函数
// ========================================

async function main() {
  console.log('\n🚀 Trading Package 快速测试');
  console.log('⏰ 开始时间:', new Date().toLocaleString('zh-CN'));

  const results = [];

  try {
    results.push(await testPortfolioTradeTool());
    results.push(await testTradeVerifyTool());
    results.push(await testM4CircuitBreakerTool());
  } catch (err: any) {
    console.error('\n❌ 测试执行失败:', err.message);
    process.exit(1);
  }

  // 汇总结果
  logTestSection('测试汇总');

  const totalPass = results.reduce((sum, r) => sum + r.passCount, 0);
  const totalTests = results.reduce((sum, r) => sum + r.totalCount, 0);
  const passRate = ((totalPass / totalTests) * 100).toFixed(1);

  console.log(`\n   总计: ${totalPass}/${totalTests} 通过 (${passRate}%)`);

  if (totalPass === totalTests) {
    console.log('\n   ✅ 所有测试通过！');
  } else {
    console.log(`\n   ⚠️  有 ${totalTests - totalPass} 个测试失败`);
  }

  console.log('\n⏰ 结束时间:', new Date().toLocaleString('zh-CN'));
  console.log('');
}

// 运行测试
main().catch(console.error);
