# 统一 ETL 数据更新 API

## 目标

将 5 个功能重叠的 ETL 脚本合并为一个统一入口 `POST /api/data/update`，调用方传参控制行为，后端内联执行（不通过 subprocess）。

## 5 个旧脚本现状

| 脚本 | 行数 | stock 来源 | 拉取天数 | 删除 |
|------|------|-----------|---------|------|
| daily_update.py | 71 | DB 所有A股 | 5天增量 | ✅ |
| download_5year_data.py | 124 | DB 有数据的所有A股 | 1825天 | ✅ |
| fetch_hs300_data.py | 134 | akshare拉HS300成分股+入库 | 730天 | ✅ |
| sync_portfolio_stocks.py | 248 | portfolio.json | 500天 | ✅ |
| sync_watchlist_stocks.py | 256 | watchlist.json | 500天 | ✅ |

所有脚本都依赖 `Database` + `KlineFetcher`，只是 source 和 days 不同。

## API 设计

### `POST /api/data/update`

```json
// Request
{
  "source": "portfolio",   // "portfolio" | "watchlist" | "hs300" | "all"
  "days": 500,             // 拉取天数
  "async": false,          // false=同步返回, true=返回job_id
  "force": false           // false=跳过已完整数据, true=强制全拉
}
```

```json
// Response (sync)
{
  "success": true,
  "source": "portfolio",
  "days": 500,
  "total": 10,      // 总股票数
  "updated": 7,     // 实际更新数
  "skipped": 3,     // 数据已完整，跳过
  "failed": 0,      // 拉取失败
  "details": [
    {
      "symbol": "600519",
      "name": "贵州茅台",
      "status": "updated",       // updated | skipped | failed
      "existing_days": 480,      // 已有数据天数
      "new_days": 20,            // 新增数据天数
      "error": null
    }
  ]
}
```

```json
// Response (async)
{
  "success": true,
  "job_id": "abc12345",
  "message": "任务已提交，请轮询 GET /api/job/<job_id>"
}
```

### Source 解析逻辑

| source | 股票列表获取方式 |
|--------|-----------------|
| `portfolio` | 读取 `../.pi-invest/portfolio.json` → holdings → 过滤A股 |
| `watchlist` | 读取 `../.pi-invest/watchlist.json` → items → 过滤A股 |
| `hs300` | `akshare.index_stock_cons_csindex("000300")` → DB stocks表 |
| `all` | `db.get_all_symbols(market='A')` |

### 增量检查逻辑（force=false 时）

对每只股票：
1. 查 `daily_klines` 表：`SELECT COUNT(*), MIN(date), MAX(date) FROM daily_klines WHERE symbol=?`
2. 计算 `缺失天数 = days - 已有天数`
3. `缺失天数 ≤ 0` → `skipped`
4. `缺失天数 > 0` → 调 `KlineFetcher.run(symbols=[symbol], days=days)` → `updated`

### 异步模式

复用现有 `_create_job` + `_run_script_async` 机制：不调用 subprocess 脚本，而是起 daemon thread 执行内联逻辑。

## 实现计划

1. **server.py**：新增 `POST /api/data/update` 端点，内联实现 source 解析 + 增量检查 + KlineFetcher 调用
2. **删除旧端点**：移除 `/api/data/update`(旧)、`/api/data/download-history`、`/api/data/fetch-hs300`、`/api/data/sync-portfolio`、`/api/data/sync-watchlist` 五个端点
3. **删除旧脚本**：移除 5 个旧 .py 文件
4. **更新 TypeScript client**：`quant-api-client.ts` 新增 `updateData()` 方法
5. **更新 TypeScript service**：`quant-service.ts` 适配新端点

## 不变的部分

- `KlineFetcher.run()` 逻辑不变
- `Database` 不变
- `stock-db/stocks.db` 表结构不变
- 因子计算、信号生成等下游脚本不受影响
