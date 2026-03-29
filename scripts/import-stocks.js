#!/usr/bin/env node
import { StockDBService } from '../dist/services/stock-db/index.js';

const db = new StockDBService('.pi-invest');
console.log('📥 导入 A 股数据...');
const count = await db.updateAStocks();
console.log(`✅ 完成: ${count} 只股票`);
