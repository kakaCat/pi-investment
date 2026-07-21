-- 数据库索引创建脚本
-- 用于优化 quantsys-v2 查询性能

-- ============================================================================
-- 1. K线数据表索引
-- ============================================================================

-- 优化按股票代码和日期范围查询
-- 用于: KlineRepository.get_daily_klines, get_daily_klines_batch
CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol_date
ON quant.daily_klines(symbol, trade_date);

-- 优化获取最新K线（避免排序）
-- 用于: KlineRepository.get_latest_daily_kline
CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol_date_desc
ON quant.daily_klines(symbol, trade_date DESC);

-- 检查索引是否创建成功
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'quant'
  AND tablename = 'daily_klines'
ORDER BY indexname;

-- ============================================================================
-- 2. 因子值表索引
-- ============================================================================

-- 优化按股票和日期查询因子
-- 用于: FactorRepository.get_factors, get_factors_batch
CREATE INDEX IF NOT EXISTS idx_factor_values_symbol_date
ON quant.factor_values(symbol, factor_date);

-- 优化因子历史查询
-- 用于: FactorRepository.get_factor_history
CREATE INDEX IF NOT EXISTS idx_factor_values_symbol_name_date
ON quant.factor_values(symbol, factor_name, factor_date);

-- 优化按因子名称和日期查询（用于覆盖率统计）
CREATE INDEX IF NOT EXISTS idx_factor_values_name_date
ON quant.factor_values(factor_name, factor_date);

-- 检查索引是否创建成功
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'quant'
  AND tablename = 'factor_values'
ORDER BY indexname;

-- ============================================================================
-- 3. 交易记录表索引
-- ============================================================================

-- 优化按股票查询交易记录
-- 用于: PortfolioRepository.get_trades_by_symbol
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time
ON quant.trades(symbol, trade_time DESC);

-- 优化按日期范围查询交易
CREATE INDEX IF NOT EXISTS idx_trades_time
ON quant.trades(trade_time DESC);

-- 检查索引是否创建成功
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'quant'
  AND tablename = 'trades'
ORDER BY indexname;

-- ============================================================================
-- 4. 信号表索引
-- ============================================================================

-- 优化按股票和日期查询信号
CREATE INDEX IF NOT EXISTS idx_signals_symbol_date
ON quant.signals(symbol, signal_date DESC);

-- 优化按日期查询所有信号
CREATE INDEX IF NOT EXISTS idx_signals_date
ON quant.signals(signal_date DESC);

-- 检查索引是否创建成功
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'quant'
  AND tablename = 'signals'
ORDER BY indexname;

-- ============================================================================
-- 5. 持仓表索引
-- ============================================================================

-- 优化按股票查询持仓
CREATE INDEX IF NOT EXISTS idx_holdings_symbol
ON quant.portfolio_holdings(symbol);

-- 优化查询所有持仓
CREATE INDEX IF NOT EXISTS idx_holdings_updated
ON quant.portfolio_holdings(updated_at DESC);

-- ============================================================================
-- 6. 验证索引创建
-- ============================================================================

-- 查看所有quant schema的索引
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes
WHERE schemaname = 'quant'
ORDER BY tablename, indexname;

-- 查看索引使用统计（需要运行一段时间后查看）
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'quant'
ORDER BY idx_scan DESC;

-- ============================================================================
-- 7. 性能分析
-- ============================================================================

-- 分析表统计信息（建议在创建索引后运行）
ANALYZE quant.daily_klines;
ANALYZE quant.factor_values;
ANALYZE quant.trades;
ANALYZE quant.signals;
ANALYZE quant.portfolio_holdings;

-- 查看表大小
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as indexes_size
FROM pg_tables
WHERE schemaname = 'quant'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ============================================================================
-- 8. 慢查询监控设置
-- ============================================================================

-- 启用慢查询日志（需要超级用户权限）
-- ALTER SYSTEM SET log_min_duration_statement = 100;  -- 记录超过100ms的查询
-- SELECT pg_reload_conf();

-- 查看当前配置
SHOW log_min_duration_statement;

-- ============================================================================
-- 完成
-- ============================================================================

SELECT 'Index creation completed successfully!' as status;
