/**
 * 测试K线缓存
 */
import { StockDBService } from './src/services/stock-db/stock-db-service.js';
import { KlineCacheService } from './src/services/stock-db/kline-cache-service.js';

async function test() {
  const db = new StockDBService('.pi-invest');
  const cache = new KlineCacheService(db);

  console.log('\n=== 测试K线缓存 ===\n');

  const symbol = '600519'; // 茅台
  const endDate = new Date().toISOString().split('T')[0];
  const startDate = '2024-01-01';

  // 1. 首次拉取（从API）
  console.log(`1. 首次拉取 ${symbol} (${startDate} ~ ${endDate})`);
  const t1 = Date.now();
  const data1 = await cache.getHistory(symbol, startDate, endDate);
  console.log(`   ✓ 耗时: ${Date.now() - t1}ms, 数据: ${data1.length} 条\n`);

  // 2. 再次拉取（从缓存）
  console.log(`2. 再次拉取 ${symbol} (从缓存)`);
  const t2 = Date.now();
  const data2 = await cache.getHistory(symbol, startDate, endDate);
  console.log(`   ✓ 耗时: ${Date.now() - t2}ms, 数据: ${data2.length} 条\n`);

  // 3. 增量更新
  console.log(`3. 增量更新 ${symbol}`);
  const updated = await cache.updateSymbol(symbol);
  console.log(`   ✓ 新增: ${updated} 条\n`);

  db.close();
  console.log('✓ 测试完成\n');
}

test().catch(console.error);
