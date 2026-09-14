-- Database Cleanup Script
-- Generated: 2026-09-14T14:32:30.928Z
-- Purpose: Remove 31 empty tables + 29 backup tables

-- ============================================
-- PART 1: Empty Tables (31 tables)
-- ============================================

-- Public schema empty tables (9 tables)
DROP TABLE IF EXISTS public.factor_computation_log;
DROP TABLE IF EXISTS public.factor_performance;
DROP TABLE IF EXISTS public.signal_execution;
DROP TABLE IF EXISTS public.strategy_backtest;
DROP TABLE IF EXISTS public.strategy_execution_log;
DROP TABLE IF EXISTS public.strategy_performance;
DROP TABLE IF EXISTS public.strategy_signals;
DROP TABLE IF EXISTS public.task_delivery_backlog;
DROP TABLE IF EXISTS public.task_dependencies;

-- Quant schema empty tables (22 tables)
DROP TABLE IF EXISTS quant.agent_logs;
DROP TABLE IF EXISTS quant.approval_rules;
DROP TABLE IF EXISTS quant.apscheduler_jobs;
DROP TABLE IF EXISTS quant.automation_logs;
DROP TABLE IF EXISTS quant.condition_monitors;
DROP TABLE IF EXISTS quant.condition_results;
DROP TABLE IF EXISTS quant.condition_rules;
DROP TABLE IF EXISTS quant.daily_quotes;
DROP TABLE IF EXISTS quant.data_snapshots;
DROP TABLE IF EXISTS quant.factors;
DROP TABLE IF EXISTS quant.ml_predictions;
DROP TABLE IF EXISTS quant.operation_audit;
DROP TABLE IF EXISTS quant.pool_game_metrics;
DROP TABLE IF EXISTS quant.pool_health_history;
DROP TABLE IF EXISTS quant.raw_klines;
DROP TABLE IF EXISTS quant.risk_metrics;
DROP TABLE IF EXISTS quant.scheduler_catchup_log;
DROP TABLE IF EXISTS quant.signal_executions;
DROP TABLE IF EXISTS quant.strategy_performance;
DROP TABLE IF EXISTS quant.strategy_validation_reports;
DROP TABLE IF EXISTS quant.task_dependencies;
DROP TABLE IF EXISTS quant.trading_signals;

-- ============================================
-- PART 2: Backup Tables (29 tables)
-- ============================================

-- Test/pseudo backup tables (8 tables)
DROP TABLE IF EXISTS public.bak_testpseudo_w23c70356_quality;
DROP TABLE IF EXISTS quant.bak_testpseudo_w23c70356_daily_klines;
DROP TABLE IF EXISTS quant.bak_testpseudo_w23c70356_factor_values;
DROP TABLE IF EXISTS quant.bak_testpseudo_w23c70356_stocks;

-- Data fix backup tables (5 tables)
DROP TABLE IF EXISTS quant.bak_amtfix_w23c70356;
DROP TABLE IF EXISTS quant.bak_index_rows_w_f4aa1f6a;
DROP TABLE IF EXISTS quant.bak_indexamt_w23c70356;
DROP TABLE IF EXISTS quant.bak_starvol_vol_w23c70356;
DROP TABLE IF EXISTS quant.tmp_volfix_noamount;

-- Daily klines backup tables (6 tables)
DROP TABLE IF EXISTS quant.daily_klines_amount_backup_20260910;
DROP TABLE IF EXISTS quant.daily_klines_amt_backup_20260910;
DROP TABLE IF EXISTS quant.daily_klines_polluted_backup_20260901;
DROP TABLE IF EXISTS quant.daily_klines_vol_backup2_20260910;
DROP TABLE IF EXISTS quant.daily_klines_vol_backup3_20260910;
DROP TABLE IF EXISTS quant.daily_klines_vol_backup_20260910;

-- Simulation account backup tables (6 tables)
DROP TABLE IF EXISTS quant.sim_calibration_backup_20260723;
DROP TABLE IF EXISTS quant.sim_snapshot_backup_20260911_wc41;
DROP TABLE IF EXISTS quant.simulation_account_backup_20260629;
DROP TABLE IF EXISTS quant.simulation_account_backup_final;
DROP TABLE IF EXISTS quant.simulation_positions_backup_20260629;
DROP TABLE IF EXISTS quant.simulation_positions_backup_final;
DROP TABLE IF EXISTS quant.simulation_trades_backup_20260629;
DROP TABLE IF EXISTS quant.simulation_trades_backup_final;

-- Other backup tables (4 tables)
DROP TABLE IF EXISTS quant.event_calendar_type_backup_20260913;
DROP TABLE IF EXISTS quant.signal_tracking_invalid_backup_20260911;
DROP TABLE IF EXISTS quant.stock_fund_flow_backup_20260911;
DROP TABLE IF EXISTS quant.stock_fund_flow_quality_backup_20260913;
DROP TABLE IF EXISTS quant.stocks_backup_20260530;
DROP TABLE IF EXISTS quant.strategy_stock_matching_backup_20260913;

-- ============================================
-- Summary
-- ============================================
-- Total tables dropped: 60
-- - Empty tables: 31
-- - Backup tables: 29
