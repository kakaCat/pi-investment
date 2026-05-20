-- PostgreSQL schema for the internal quant research/signal platform.
-- Run against the quant database, for example:
--   createdb quant_investment
--   psql quant_investment -f scripts/postgres/create-quant-db.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS quant;
CREATE SCHEMA IF NOT EXISTS quant_compat;

CREATE TABLE IF NOT EXISTS quant.stocks (
  symbol TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  market TEXT NOT NULL,
  industry TEXT,
  sector TEXT,
  market_cap DOUBLE PRECISION,
  pe DOUBLE PRECISION,
  pb DOUBLE PRECISION,
  total_mv DOUBLE PRECISION,
  circulating_mv DOUBLE PRECISION,
  is_st BOOLEAN NOT NULL DEFAULT FALSE,
  is_suspended BOOLEAN NOT NULL DEFAULT FALSE,
  list_date DATE,
  roe DOUBLE PRECISION,
  net_profit_growth DOUBLE PRECISION,
  gross_margin DOUBLE PRECISION,
  debt_ratio DOUBLE PRECISION,
  avg_turnover_rate DOUBLE PRECISION,
  avg_volume DOUBLE PRECISION,
  avg_amount DOUBLE PRECISION,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quant.daily_klines (
  symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
  trade_date DATE NOT NULL,
  open DOUBLE PRECISION,
  high DOUBLE PRECISION,
  low DOUBLE PRECISION,
  close DOUBLE PRECISION,
  volume DOUBLE PRECISION,
  amount DOUBLE PRECISION,
  turnover_rate DOUBLE PRECISION,
  PRIMARY KEY (symbol, trade_date)
);

CREATE TABLE IF NOT EXISTS quant.minute_klines (
  symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL,
  open DOUBLE PRECISION,
  high DOUBLE PRECISION,
  low DOUBLE PRECISION,
  close DOUBLE PRECISION,
  volume DOUBLE PRECISION,
  amount DOUBLE PRECISION,
  PRIMARY KEY (symbol, ts)
);

CREATE TABLE IF NOT EXISTS quant.daily_quotes (
  symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
  quote_date DATE NOT NULL,
  close DOUBLE PRECISION,
  volume DOUBLE PRECISION,
  amount DOUBLE PRECISION,
  turnover_rate DOUBLE PRECISION,
  PRIMARY KEY (symbol, quote_date)
);

CREATE TABLE IF NOT EXISTS quant.factor_values (
  symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
  factor_date DATE NOT NULL,
  factor_name TEXT NOT NULL,
  factor_value DOUBLE PRECISION,
  PRIMARY KEY (symbol, factor_date, factor_name)
);

CREATE TABLE IF NOT EXISTS quant.signals (
  id BIGSERIAL PRIMARY KEY,
  signal_date DATE NOT NULL,
  symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
  name TEXT NOT NULL,
  action TEXT NOT NULL,
  action_type INTEGER NOT NULL,
  strategy_id TEXT NOT NULL,
  price DOUBLE PRECISION,
  reason TEXT,
  confidence DOUBLE PRECISION,
  indicators JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quant.jobs (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  status TEXT NOT NULL,
  params JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB,
  error TEXT,
  logs JSONB NOT NULL DEFAULT '[]'::jsonb,
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS quant.schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO quant.schema_migrations (version)
VALUES ('2026-05-19-create-quant-schema')
ON CONFLICT (version) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_quant_stocks_market ON quant.stocks(market);
CREATE INDEX IF NOT EXISTS idx_quant_stocks_industry ON quant.stocks(industry);
CREATE INDEX IF NOT EXISTS idx_quant_stocks_sector ON quant.stocks(sector);
CREATE INDEX IF NOT EXISTS idx_quant_stocks_market_cap ON quant.stocks(market_cap);
CREATE INDEX IF NOT EXISTS idx_quant_stocks_pe ON quant.stocks(pe);
CREATE INDEX IF NOT EXISTS idx_quant_stocks_updated_at ON quant.stocks(updated_at);

CREATE INDEX IF NOT EXISTS idx_quant_daily_klines_trade_date ON quant.daily_klines(trade_date);
CREATE INDEX IF NOT EXISTS idx_quant_daily_klines_symbol_date_desc
  ON quant.daily_klines(symbol, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_quant_minute_klines_symbol_ts_desc
  ON quant.minute_klines(symbol, ts DESC);

CREATE INDEX IF NOT EXISTS idx_quant_daily_quotes_quote_date ON quant.daily_quotes(quote_date);

CREATE INDEX IF NOT EXISTS idx_quant_factor_values_factor_date ON quant.factor_values(factor_date);
CREATE INDEX IF NOT EXISTS idx_quant_factor_values_symbol_date
  ON quant.factor_values(symbol, factor_date);
CREATE INDEX IF NOT EXISTS idx_quant_factor_values_name_date
  ON quant.factor_values(factor_name, factor_date);

CREATE INDEX IF NOT EXISTS idx_quant_signals_signal_date ON quant.signals(signal_date);
CREATE INDEX IF NOT EXISTS idx_quant_signals_symbol ON quant.signals(symbol);
CREATE INDEX IF NOT EXISTS idx_quant_signals_strategy ON quant.signals(strategy_id);
CREATE INDEX IF NOT EXISTS idx_quant_signals_action_type ON quant.signals(action_type);
CREATE INDEX IF NOT EXISTS idx_quant_signals_created_at ON quant.signals(created_at);
CREATE INDEX IF NOT EXISTS idx_quant_signals_indicators_gin ON quant.signals USING GIN(indicators);

CREATE INDEX IF NOT EXISTS idx_quant_jobs_type ON quant.jobs(type);
CREATE INDEX IF NOT EXISTS idx_quant_jobs_status ON quant.jobs(status);
CREATE INDEX IF NOT EXISTS idx_quant_jobs_created_at ON quant.jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_quant_jobs_params_gin ON quant.jobs USING GIN(params);

CREATE OR REPLACE VIEW quant_compat.stocks AS
SELECT
  symbol,
  name,
  market,
  industry,
  sector,
  market_cap,
  pe,
  pb,
  total_mv,
  circulating_mv,
  is_st::integer AS is_st,
  is_suspended::integer AS is_suspended,
  list_date::text AS list_date,
  roe,
  net_profit_growth,
  gross_margin,
  debt_ratio,
  avg_turnover_rate,
  avg_volume,
  avg_amount,
  updated_at::text AS updated_at
FROM quant.stocks;

CREATE OR REPLACE VIEW quant_compat.daily_klines AS
SELECT
  symbol,
  trade_date::text AS date,
  open,
  high,
  low,
  close,
  volume,
  amount,
  turnover_rate
FROM quant.daily_klines;

CREATE OR REPLACE VIEW quant_compat.factor_values AS
SELECT
  symbol,
  factor_date::text AS date,
  factor_name,
  factor_value
FROM quant.factor_values;

CREATE OR REPLACE VIEW quant_compat.daily_quotes AS
SELECT
  symbol,
  quote_date::text AS date,
  close,
  volume,
  amount,
  turnover_rate
FROM quant.daily_quotes;

CREATE OR REPLACE VIEW quant_compat.signals AS
SELECT
  id,
  signal_date::text AS date,
  symbol,
  name,
  action,
  action_type,
  strategy_id,
  price,
  reason,
  confidence,
  indicators::text AS indicators,
  created_at::text AS created_at
FROM quant.signals;

COMMIT;
