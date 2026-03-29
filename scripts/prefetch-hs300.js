/**
 * 批量预取沪深 300 指数成分股的历史 K 线数据
 */
import { StockDBService, KlineCacheService } from '../src/services/stock-db/index.js';
import { callPython } from '../src/infrastructure/tools/invest-tools.js';

async function prefetchHS300() {
  const db = new StockDBService('.pi-invest');
  const cache = new KlineCacheService(db);

  console.log('🔍 获取沪深 300 成分股列表...');
  // 通过 Python 桥获取沪深 300 成分股
  // 注意：akshare 接口为 index_stock_cons_em
  const hs300Raw = await callPython('get_concept_stocks', { concept: '沪深300' });
  const hs300Data = JSON.parse(hs300Raw);

  let symbols = [];
  if (hs300Data.data && Array.isArray(hs300Data.data)) {
    symbols = hs300Data.data.map(s => s.code);
  } else {
    // 如果概念接口失败，尝试硬编码一部分或从数据库按市值取前300
    console.warn('⚠️ 无法通过接口获取沪深 300，改为从数据库获取市值前 300 的股票...');
    const topStocks = db.filter({ min_market_cap: 100 }); // 简单演示
    symbols = topStocks.slice(0, 300).map(s => s.symbol);
  }

  console.log(`🚀 开始预取 ${symbols.length} 只股票的历史数据 (最近 2 年)...`);
  const startDate = '2024-01-01';
  const endDate = new Date().toISOString().split('T')[0];

  let success = 0;
  let fail = 0;

  // 分批处理，避免并发过大
  const batchSize = 5;
  for (let i = 0; i < symbols.length; i += batchSize) {
    const batch = symbols.slice(i, i + batchSize);
    await Promise.all(batch.map(async (symbol) => {
      try {
        process.stdout.write(`[${i + symbols.indexOf(symbol) + 1}/${symbols.length}] 正在抓取 ${symbol}... `);
        const data = await cache.getHistory(symbol, startDate, endDate);
        if (data && data.length > 0) {
          console.log(`✅ ${data.length} 条`);
          success++;
        } else {
          console.log('❌ 无数据');
          fail++;
        }
      } catch (err) {
        console.log(`❌ 失败: ${err.message}`);
        fail++;
      }
    }));
  }

  console.log('\n--- 预取完成 ---');
  console.log(`成功: ${success}`);
  console.log(`失败: ${fail}`);
  db.close();
}

prefetchHS300().catch(console.error);
