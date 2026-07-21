================================================================================
数据库查询优化分析报告
================================================================================

## 🔴 关键问题 (CRITICAL)

### DataService.batch_get_latest_factors
- **问题**: N+1查询问题：循环调用get_latest_factors
- **频率**: HIGH
- **优化建议**: 改为单次批量查询

## 🟠 高影响问题 (HIGH)

### KlineRepository.get_daily_klines
- **问题**: 频繁的范围查询，需要复合索引
- **频率**: VERY_HIGH

### KlineRepository.get_daily_klines_batch
- **问题**: 批量查询多个股票，可能导致全表扫描
- **频率**: HIGH
- **优化建议**: 使用复合索引 + 考虑分区表

### FactorRepository.get_latest_factors
- **问题**: 子查询执行两次，且子查询可能不使用索引
- **频率**: VERY_HIGH
- **优化建议**: 使用窗口函数或JOIN优化

### DataService.get_stock_full_data
- **问题**: 顺序执行多个查询：stock_info, klines, factors, signals, stats
- **频率**: HIGH
- **优化建议**: 使用缓存 + 考虑并行查询（连接池）

## 🟡 中等影响问题 (MEDIUM)

### KlineRepository.get_latest_daily_kline
- **问题**: 每次都需要排序，即使只取一条
- **频率**: VERY_HIGH
- **优化建议**: 复合索引 (symbol, trade_date DESC) 可避免排序

### KlineRepository.get_trading_days
- **问题**: DISTINCT 需要排序和去重，成本较高
- **频率**: MEDIUM
- **优化建议**: 考虑维护单独的交易日历表

### FactorRepository.get_factors
- **问题**: 每次查询返回多行，需要在应用层聚合
- **频率**: VERY_HIGH

### FactorRepository.get_factors_batch
- **问题**: 批量查询，但返回大量行需要应用层分组
- **频率**: HIGH
- **优化建议**: 已经是批量查询，主要优化在索引

### FactorRepository.get_factor_history
- **问题**: 需要复合索引支持
- **频率**: MEDIUM

### PortfolioRepository.get_trades_by_symbol
- **问题**: 需要索引支持排序
- **频率**: MEDIUM

## 📊 索引建议

以下索引可以显著提升查询性能：

### 1. idx_daily_klines_symbol_date
- **表**: quant.daily_klines
- **列**: symbol, trade_date
- **原因**: 优化按股票代码和日期范围查询
- **SQL**:
```sql
CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol_date ON quant.daily_klines(symbol, trade_date);
```

### 2. idx_daily_klines_symbol_date_desc
- **表**: quant.daily_klines
- **列**: symbol, trade_date DESC
- **原因**: 优化获取最新K线，避免排序
- **SQL**:
```sql
CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol_date_desc ON quant.daily_klines(symbol, trade_date DESC);
```

### 3. idx_factor_values_symbol_date
- **表**: quant.factor_values
- **列**: symbol, factor_date
- **原因**: 优化按股票和日期查询因子
- **SQL**:
```sql
CREATE INDEX IF NOT EXISTS idx_factor_values_symbol_date ON quant.factor_values(symbol, factor_date);
```

### 4. idx_factor_values_symbol_name_date
- **表**: quant.factor_values
- **列**: symbol, factor_name, factor_date
- **原因**: 优化因子历史查询
- **SQL**:
```sql
CREATE INDEX IF NOT EXISTS idx_factor_values_symbol_name_date ON quant.factor_values(symbol, factor_name, factor_date);
```

### 5. idx_trades_symbol_time
- **表**: quant.trades
- **列**: symbol, trade_time DESC
- **原因**: 优化按股票查询交易记录
- **SQL**:
```sql
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON quant.trades(symbol, trade_time DESC);
```

## ✅ 优化查询示例

### FactorRepository.get_latest_factors (优化)
```sql
WITH latest AS (
                            SELECT symbol, MAX(factor_date) as max_date
                            FROM quant.factor_values
                            WHERE symbol = %s
                            GROUP BY symbol
                        )
                        SELECT fv.factor_name, fv.factor_value
                        FROM quant.factor_values fv
                        JOIN latest l ON fv.symbol = l.symbol AND fv.factor_date = l.max_date
```

### DataService.batch_get_latest_factors (优化)
```sql
WITH latest_dates AS (
                            SELECT symbol, MAX(factor_date) as max_date
                            FROM quant.factor_values
                            WHERE symbol = ANY(%s)
                            GROUP BY symbol
                        )
                        SELECT fv.symbol, fv.factor_name, fv.factor_value
                        FROM quant.factor_values fv
                        JOIN latest_dates ld ON fv.symbol = ld.symbol AND fv.factor_date = ld.max_date
```

## 💡 通用优化建议

1. **连接池配置**
   - 增加连接池大小以支持并发查询
   - 配置合理的连接超时和空闲超时

2. **查询日志**
   - 启用慢查询日志 (log_min_duration_statement = 100ms)
   - 定期分析慢查询并优化

3. **批量操作**
   - 使用 execute_batch 替代循环插入
   - 批量查询时使用 ANY(%s) 或 IN 子句

4. **缓存策略**
   - 对频繁查询的数据使用缓存（如最新K线、因子值）
   - 设置合理的TTL避免数据过期

5. **分区表**
   - 对大表（如daily_klines）考虑按日期分区
   - 提升范围查询和数据维护性能

6. **物化视图**
   - 对复杂聚合查询使用物化视图
   - 定期刷新以保持数据新鲜度

## 📈 性能监控建议

```sql
-- 查看表大小
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'quant'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 查看索引使用情况
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'quant'
ORDER BY idx_scan DESC;

-- 查看未使用的索引
SELECT schemaname, tablename, indexname
FROM pg_stat_user_indexes
WHERE schemaname = 'quant' AND idx_scan = 0;
```
