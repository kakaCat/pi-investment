#!/usr/bin/env tsx
/**
 * Trading Package 简化测试脚本
 *
 * 运行: npx tsx scripts/simple-test.ts
 */

import { PortfolioTradeTool } from '../src/tools/PortfolioTradeTool/PortfolioTradeTool';
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

  getRiskMetrics: async (params: any) => ({
    max_drawdown: -5.2,
    volatility: 15.3,
    sharpe_ratio: 1.2,
  }),

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

console.log('\n' + '='.repeat(70));
console.log('  🚀 Trading Package 简化测试');
console.log('='.repeat(70));
console.log(`  ⏰ 开始时间: ${new Date().toLocaleString('zh-CN')}\n`);

let totalTests = 0;
let passedTests = 0;

// ========================================
// 测试 1: PortfolioTradeTool
// ========================================

console.log('📦 测试 PortfolioTradeTool\n');

const portfolioTool = new PortfolioTradeTool(mockQv2 as any, mockOsMemory, mockCtx);

// 测试 1.1: 缺少 action
totalTests++;
console.log('1️⃣  缺少 action 参数');
const result1 = await portfolioTool.call({} as any);
if (!result1.success && result1.error?.field === 'action') {
  console.log('   ✅ 通过 - 正确拦截缺少 action\n');
  passedTests++;
} else {
  console.log('   ❌ 失败 - 应该拦截缺少 action\n');
}

// 测试 1.2: 错误的 action
totalTests++;
console.log('2️⃣  错误的 action (小写)');
const result2 = await portfolioTool.call({
  action: 'buy',
  symbol: '600519',
  quantity: 100,
} as any);
if (!result2.success && result2.error?.field === 'action') {
  console.log('   ✅ 通过 - 正确拦截小写 action\n');
  passedTests++;
} else {
  console.log('   ❌ 失败 - 应该拦截小写 action\n');
}

// 测试 1.3: 错误的 symbol
totalTests++;
console.log('3️⃣  错误的 symbol (含前缀 SH)');
const result3 = await portfolioTool.call({
  action: 'BUY',
  symbol: 'SH600519',
  quantity: 100,
} as any);
if (!result3.success && result3.error?.field === 'symbol') {
  console.log('   ✅ 通过 - 正确拦截错误 symbol 格式\n');
  passedTests++;
} else {
  console.log('   ❌ 失败 - 应该拦截错误 symbol 格式\n');
}

// 测试 1.4: 错误的 quantity
totalTests++;
console.log('4️⃣  错误的 quantity (非100倍数)');
const result4 = await portfolioTool.call({
  action: 'BUY',
  symbol: '600519',
  quantity: 50,
} as any);
if (!result4.success && result4.error?.field === 'quantity') {
  console.log('   ✅ 通过 - 正确拦截非100倍数 quantity\n');
  passedTests++;
} else {
  console.log('   ❌ 失败 - 应该拦截非100倍数 quantity\n');
}

// 测试 1.5: 正常买入（会被交易时段拦截）
totalTests++;
console.log('5️⃣  正常买入交易');
try {
  const result5 = await portfolioTool.call({
    action: 'BUY',
    symbol: '600519',
    quantity: 100,
    price: 1850.0,
    reason: 'R-001: 测试买入',
  });

  if (!result5.success && result5.error?.issue?.includes('交易时段')) {
    console.log('   ✅ 通过 - 交易时段校验生效（非交易时段）\n');
    passedTests++;
  } else if (result5.success && result5.data?.order_id) {
    console.log('   ✅ 通过 - 交易执行成功');
    console.log(`   📊 订单ID: ${result5.data.order_id}`);
    console.log(`   📊 成交价: ${result5.data.price}\n`);
    passedTests++;
  } else {
    console.log('   ❌ 失败 - 交易执行失败\n');
  }
} catch (err: any) {
  if (err.message.includes('交易时段')) {
    console.log('   ✅ 通过 - 交易时段校验生效（非交易时段）\n');
    passedTests++;
  } else {
    console.log(`   ❌ 失败 - 意外错误: ${err.message}\n`);
  }
}

// 测试 1.6: toDSHToolDefinition 转换
totalTests++;
console.log('6️⃣  toDSHToolDefinition 转换');
const dshDef = portfolioTool.toDSHToolDefinition();
if (
  dshDef.name === 'portfolio_trade' &&
  dshDef.description &&
  dshDef.parameters &&
  typeof dshDef.execute === 'function'
) {
  console.log('   ✅ 通过 - DSH 工具定义正确\n');
  passedTests++;
} else {
  console.log('   ❌ 失败 - DSH 工具定义不完整\n');
}

// ========================================
// 测试 2: M4CircuitBreakerTool
// ========================================

console.log('\n📦 测试 M4CircuitBreakerTool\n');

const circuitBreakerTool = new M4CircuitBreakerTool(mockQv2 as any, mockOsMemory);

// 测试 2.1: 正常情况（未触发熔断）
totalTests++;
console.log('1️⃣  正常情况（回撤 < 8%）');
const cbResult1 = await circuitBreakerTool.call({
  account_name: 'agent_virtual',
});
if (cbResult1.success && !cbResult1.data?.triggered) {
  console.log('   ✅ 通过 - 熔断检查正常');
  console.log(`   📊 最大回撤: ${cbResult1.data.max_drawdown}%`);
  console.log(`   📊 是否触发: ${cbResult1.data.triggered}\n`);
  passedTests++;
} else {
  console.log('   ❌ 失败 - 熔断检查失败\n');
}

// 测试 2.2: 极端情况（触发熔断）
totalTests++;
console.log('2️⃣  极端情况（回撤 > 8%）');
const mockQv2Extreme = {
  ...mockQv2,
  getRiskMetrics: async (params: any) => ({
    max_drawdown: -9.5,
    volatility: 25.0,
    sharpe_ratio: -0.5,
  }),
  getPerformanceMetrics: async () => ({
    drawdown_60d: -9.5,
    return_60d: -5.0,
  }),
};
const circuitBreakerTool2 = new M4CircuitBreakerTool(mockQv2Extreme as any, mockOsMemory);
const cbResult2 = await circuitBreakerTool2.call({
  account_name: 'agent_virtual',
});
if (cbResult2.success && cbResult2.data?.triggered) {
  console.log('   ✅ 通过 - 熔断正确触发');
  console.log(`   📊 最大回撤: ${cbResult2.data.max_drawdown}%`);
  console.log(`   📊 建议操作: ${cbResult2.data.action}\n`);
  passedTests++;
} else {
  console.log('   ❌ 失败 - 熔断应该触发但未触发\n');
}

// ========================================
// 测试汇总
// ========================================

console.log('='.repeat(70));
console.log('  📊 测试汇总');
console.log('='.repeat(70));
console.log(`  总计: ${passedTests}/${totalTests} 通过 (${((passedTests/totalTests)*100).toFixed(1)}%)`);

if (passedTests === totalTests) {
  console.log('  ✅ 所有测试通过！');
} else {
  console.log(`  ⚠️  有 ${totalTests - passedTests} 个测试失败`);
}

console.log(`  ⏰ 结束时间: ${new Date().toLocaleString('zh-CN')}`);
console.log('='.repeat(70) + '\n');

process.exit(passedTests === totalTests ? 0 : 1);
