#!/usr/bin/env node
/**
 * 手动测试脚本：验证 quant-cli-tool 的参数校验和错误信息
 */

// 模拟 quant_cli 工具的调用
const testCases = [
  {
    name: "backtest.run 缺少 symbol 和 symbols",
    command: "backtest.run",
    params: {},
    expectedError: "backtest.run 至少需要 symbol 或 symbols 参数之一",
    expectedReason: "原因：回测需要指定股票代码才能获取历史数据并执行策略测试"
  },
  {
    name: "backtest.run 只有 symbol",
    command: "backtest.run",
    params: { symbol: "600519", days: 365 },
    expectedError: null
  },
  {
    name: "backtest.run 只有 symbols",
    command: "backtest.run",
    params: { symbols: "600519,000001", days: 365 },
    expectedError: null
  },
  {
    name: "stock.klines 缺少必填参数 symbol",
    command: "stock.klines",
    params: { limit: 10 },
    expectedError: "缺少必填参数: symbol",
    expectedReason: "原因：该参数是命令执行的必要条件"
  },
  {
    name: "stock.quote 不支持的参数",
    command: "stock.quote",
    params: { symbol: "600519", invalid_param: true },
    expectedError: "不支持的参数: invalid_param",
    expectedReason: "原因：该命令不接受此参数"
  },
  {
    name: "stock.klines limit 类型错误",
    command: "stock.klines",
    params: { symbol: "600519", limit: "not-a-number" },
    expectedError: "limit 必须是整数",
    expectedReason: "原因：该参数不接受小数或非数字值"
  }
];

console.log("=".repeat(80));
console.log("参数校验测试用例");
console.log("=".repeat(80));
console.log();

testCases.forEach((testCase, index) => {
  console.log(`测试 ${index + 1}: ${testCase.name}`);
  console.log(`  命令: ${testCase.command}`);
  console.log(`  参数: ${JSON.stringify(testCase.params)}`);
  if (testCase.expectedError) {
    console.log(`  预期错误: ${testCase.expectedError}`);
    console.log(`  预期原因: ${testCase.expectedReason}`);
  } else {
    console.log(`  预期: 校验通过`);
  }
  console.log();
});

console.log("=".repeat(80));
console.log("说明：");
console.log("1. 所有错误信息现在都包含详细的原因说明");
console.log("2. backtest.run 特别校验：至少需要 symbol 或 symbols 之一");
console.log("3. 错误信息格式：<错误描述>。原因：<详细原因>");
console.log("=".repeat(80));
