/**
 * 测试混合模式技术指标计算
 */
import { calculate_technical_indicators } from './src/infrastructure/akshare-ts/index.js';

async function test() {
  const symbol = '600519'; // 贵州茅台
  console.log(`开始测试 ${symbol} 的技术指标 (混合模式)...`);

  const start = Date.now();
  const resultJson = await calculate_technical_indicators(symbol);
  const end = Date.now();

  const result = JSON.parse(resultJson);
  console.log('--- 计算结果 ---');
  console.log(`耗时: ${end - start}ms`);
  console.log(`股票: ${result.symbol}`);
  console.log(`价格: ${result.current_price}`);
  console.log(`MA5: ${result.ma5}`);
  console.log(`MA20: ${result.ma20}`);
  console.log(`信号: ${result.signals.join(', ')}`);
  console.log(`数据日期: ${result.data_date}`);

  // 再次运行测试缓存速度
  console.log('\n第二次运行 (预期应从缓存读取)...');
  const start2 = Date.now();
  await calculate_technical_indicators(symbol);
  const end2 = Date.now();
  console.log(`第二次耗时: ${end2 - start2}ms`);
}

test().catch(console.error);
