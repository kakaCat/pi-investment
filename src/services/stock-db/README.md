# 股票数据库服务

## 功能

本地 SQLite 数据库，存储 A 股/港股基础信息，支持快速筛选。

## 使用

### 初始化和更新

```typescript
import { StockDBService } from './stock-db-service.js';

const db = new StockDBService('.pi-invest');

// 首次使用：更新股票列表
await db.updateAStocks();  // 更新 A 股（约 5000 只）
```

### 筛选股票池

```typescript
// 示例 1: 低估值大盘股
const stocks = db.filter({
  market: 'A',
  min_market_cap: 100,      // 市值 > 100 亿
  max_pe: 20,               // PE < 20
  max_pb: 3,                // PB < 3
  exclude_st: true,         // 排除 ST
  list_days: 365            // 上市 > 1 年
});

// 示例 2: 银行股
const banks = db.filter({
  market: 'A',
  industry: '银行',
  exclude_st: true
});

// 示例 3: 全市场扫描
const all = db.filter({
  market: 'A',
  exclude_st: true,
  exclude_suspended: true
});
```

### 统计

```typescript
const total = db.count();        // 总数
const aCount = db.count('A');    // A 股数量
```

## 数据更新

建议每日收盘后更新一次（通过 CRON）：

```json
{
  "name": "update-stock-db",
  "schedule": "0 16 * * 1-5",
  "action": "update_stock_database"
}
```

## 性能

- 筛选 5000 只股票：< 10ms
- 更新全量数据：约 30 秒
