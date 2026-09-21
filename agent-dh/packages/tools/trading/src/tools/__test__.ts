/**
 * 工具重构验证测试
 */

import { PortfolioTradeTool } from '../tools/PortfolioTradeTool/PortfolioTradeTool';
import { M4CircuitBreakerTool } from '../tools/M4CircuitBreakerTool/M4CircuitBreakerTool';

// Mock 客户端
const mockQv2: any = {
  executeTrade: async (args: any) => ({
    order_id: 'test_order_001',
    action: args.action,
    symbol: args.symbol,
    quantity: args.quantity,
    price: 1850.0,
    amount: args.quantity * 1850.0,
    status: 'filled',
    timestamp: new Date().toISOString(),
  }),
  getRiskMetrics: async () => ({
    max_drawdown: -5.2,
  }),
  getPositions: async () => [],
};

const mockOsMemory: any = {
  search: async () => ({ memories: [] }),
  write: async () => {},
};

// Mock context
const mockCtx = {
  tools: {
    call: async (name: string, args: any) => {
      if (name === 'regime_position_limit') {
        return { verdict: 'ok', max_position_pct: 80, current_position_pct: 50 };
      }
      return {};
    },
    execute: async () => ({}),
  },
};

// 测试 1: PortfolioTradeTool 参数校验
async function testPortfolioTradeValidation() {
  console.log('🧪 测试 1: PortfolioTradeTool 参数校验');

  const tool = new PortfolioTradeTool(mockQv2, mockOsMemory, mockCtx);

  // 测试缺少 action
  const result1 = await tool.call({} as any);
  console.log('  ❌ 缺少 action:', result1.success ? '失败' : '✅ 通过');

  // 测试错误的 action
  const result2 = await tool.call({ action: 'buy', symbol: '600519', quantity: 100 } as any);
  console.log('  ❌ 错误的 action:', result2.success ? '失败' : '✅ 通过');

  // 测试错误的 symbol
  const result3 = await tool.call({ action: 'BUY', symbol: 'SH600519', quantity: 100 } as any);
  console.log('  ❌ 错误的 symbol:', result3.success ? '失败' : '✅ 通过');

  // 测试错误的 quantity
  const result4 = await tool.call({ action: 'BUY', symbol: '600519', quantity: 50 } as any);
  console.log('  ❌ 错误的 quantity:', result4.success ? '失败' : '✅ 通过');

  // 测试正确的参数
  const result5 = await tool.call({ action: 'BUY', symbol: '600519', quantity: 100 });
  console.log('  ✅ 正确的参数:', result5.success ? '✅ 通过' : '失败');
  console.log('     返回数据:', result5.data ? '有数据' : '无数据');
}

// 测试 2: M4CircuitBreakerTool
async function testCircuitBreaker() {
  console.log('\n🧪 测试 2: M4CircuitBreakerTool');

  const tool = new M4CircuitBreakerTool(mockQv2, mockOsMemory);

  // 测试空参数
  const result1 = await tool.call({});
  console.log('  ✅ 空参数:', result1.success ? '✅ 通过' : '失败');
  console.log('     max_drawdown:', result1.data?.max_drawdown);
  console.log('     triggered:', result1.data?.triggered);
}

// 测试 3: toDSHToolDefinition
function testDSHConversion() {
  console.log('\n🧪 测试 3: toDSHToolDefinition 转换');

  const tool = new PortfolioTradeTool(mockQv2, mockOsMemory, mockCtx);
  const dshDef = tool.toDSHToolDefinition();

  console.log('  ✅ name:', dshDef.name === 'portfolio_trade' ? '✅ 通过' : '失败');
  console.log('  ✅ description:', dshDef.description ? '✅ 通过' : '失败');
  console.log('  ✅ parameters:', dshDef.parameters ? '✅ 通过' : '失败');
  console.log('  ✅ output:', dshDef.output ? '✅ 通过' : '失败');
  console.log('  ✅ execute:', typeof dshDef.execute === 'function' ? '✅ 通过' : '失败');
  console.log('  ✅ render:', typeof dshDef.output.render === 'function' ? '✅ 通过' : '失败');
}

// 运行所有测试
async function runAllTests() {
  console.log('========================================');
  console.log('🚀 开始工具重构验证测试');
  console.log('========================================\n');

  try {
    await testPortfolioTradeValidation();
    await testCircuitBreaker();
    testDSHConversion();

    console.log('\n========================================');
    console.log('✅ 所有测试完成');
    console.log('========================================');
  } catch (error: any) {
    console.error('\n❌ 测试失败:', error.message);
    console.error(error.stack);
  }
}

runAllTests();
