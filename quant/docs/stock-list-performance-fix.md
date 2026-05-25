# 股票列表页性能优化

## 问题描述

股票列表页 (`/api/stocks/data-status`) 加载非常慢，需要约 25 秒才能返回数据。

## 根本原因

API 端点执行两个耗时的查询：

1. **因子统计查询**：扫描 2970 万行 `factor_values` 表，使用 `GROUP BY` 和 `COUNT(DISTINCT)` 操作
   - 耗时：~21.5 秒（PostgreSQL）
   
2. **K线统计查询**：对 5459 只股票执行 LEFT JOIN 查询 520 万行 `daily_klines` 表
   - 耗时：~3.7 秒

**总耗时：~25 秒**

## 解决方案

创建预计算的汇总表 `stock_data_summary`，存储每只股票的统计信息：

```sql
CREATE TABLE quant_compat.stock_data_summary (
    symbol TEXT PRIMARY KEY,
    factor_days INTEGER,        -- 因子数据天数
    factor_count INTEGER,       -- 因子数量
    kline_days INTEGER,         -- K线数据天数
    earliest_date TEXT,         -- 最早日期
    latest_date TEXT,          -- 最新日期
    last_updated TIMESTAMP     -- 最后更新时间
);
```

### 性能提升

- **优化前**：~25 秒
- **优化后**：~0.12 秒
- **提升**：200 倍加速

## 维护说明

汇总表需要在以下情况下刷新：

1. **每次更新股票数据后**
2. **每次计算因子后**
3. **定期维护**（建议每天一次）

### 手动刷新

#### PostgreSQL（生产环境）

```bash
psql -d quant_investment -c "
-- 更新因子统计
INSERT INTO quant_compat.stock_data_summary (symbol, factor_days, factor_count, last_updated)
SELECT
    symbol,
    COUNT(DISTINCT date) as factor_days,
    COUNT(DISTINCT factor_name) as factor_count,
    NOW() as last_updated
FROM quant_compat.factor_values
GROUP BY symbol
ON CONFLICT (symbol) DO UPDATE SET
    factor_days = EXCLUDED.factor_days,
    factor_count = EXCLUDED.factor_count,
    last_updated = EXCLUDED.last_updated;

-- 更新K线统计
UPDATE quant_compat.stock_data_summary s
SET
    kline_days = k.kline_days,
    earliest_date = k.earliest_date,
    latest_date = k.latest_date
FROM (
    SELECT
        symbol,
        COUNT(DISTINCT date) as kline_days,
        MIN(date) as earliest_date,
        MAX(date) as latest_date
    FROM quant_compat.daily_klines
    GROUP BY symbol
) k
WHERE s.symbol = k.symbol;
"
```

#### SQLite（本地开发）

```bash
python3 quant/scripts/refresh_stock_summary.py
```

### 自动刷新

将刷新脚本添加到数据更新流程中：

1. 在 `quant/scripts/scheduler.py` 中添加刷新任务
2. 在数据更新 API (`/api/data/update`) 完成后调用刷新
3. 在因子计算 API (`/api/compute/factors`) 完成后调用刷新

## 技术细节

### 查询优化历程

1. **尝试 1：添加复合索引** - 从 21.5s 降到 7.6s（65% 提升，但仍太慢）
2. **尝试 2：物化视图/汇总表** - 降到 0.12s（200x 提升）✅

### 为什么索引不够

`COUNT(DISTINCT)` 操作需要创建临时 B-tree 来去重，即使有索引也无法避免全表扫描。预计算是唯一能达到亚秒级响应的方案。

## 相关文件

- API 端点：`quant/api/server.py:2317` (`get_stocks_data_status`)
- 刷新脚本：`quant/scripts/refresh_stock_summary.py`
- 前端组件：`quant-web/src/components/StockList.tsx`

## 监控

检查汇总表的新鲜度：

```sql
SELECT 
    COUNT(*) as total_stocks,
    MAX(last_updated) as last_refresh,
    NOW() - MAX(last_updated) as age
FROM quant_compat.stock_data_summary;
```

如果 `age` 超过 24 小时，应该刷新汇总表。
