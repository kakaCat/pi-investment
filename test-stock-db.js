/**
 * 测试股票数据库
 */
import { StockDBService } from './src/services/stock-db/stock-db-service.js';

async function test() {
  const db = new StockDBService('.pi-invest');

  console.log('\n=== 测试股票数据库 ===\n');

  // 1. 更新数据
  console.log('1. 更新 A 股列表...');
  const count = await db.updateAStocks();
  console.log(`   ✓ 更新完成：${count} 只股票\n`);

  // 2. 统计
  console.log('2. 统计信息');
  console.log(`   总数：${db.count()} 只`);
  console.log(`   A 股：${db.count('A')} 只\n`);

  // 3. 筛选测试
  console.log('3. 筛选测试');

  const bigCaps = db.filter({
    market: 'A',
    min_market_cap: 1000,
    exclude_st: true
  });
  console.log(`   大盘股（市值>1000亿）：${bigCaps.length} 只`);
  console.log(`   示例：${bigCaps.slice(0, 3).map(s => s.name).join(', ')}\n`);

  const lowPE = db.filter({
    market: 'A',
    max_pe: 15,
    min_market_cap: 50,
    exclude_st: true
  });
  console.log(`   低估值（PE<15, 市值>50亿）：${lowPE.length} 只`);
  console.log(`   示例：${lowPE.slice(0, 5).map(s => `${s.name}(PE:${s.pe?.toFixed(1)})`).join(', ')}\n`);

  db.close();
  console.log('✓ 测试完成\n');
}

test().catch(console.error);
