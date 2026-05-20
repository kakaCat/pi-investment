SELECT current_database() AS database_name;

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'quant'
ORDER BY table_name;

SELECT table_schema, table_name
FROM information_schema.views
WHERE table_schema = 'quant_compat'
ORDER BY table_name;

SELECT 'quant.stocks' AS table_name, COUNT(*) AS rows FROM quant.stocks
UNION ALL SELECT 'quant.daily_klines', COUNT(*) FROM quant.daily_klines
UNION ALL SELECT 'quant.minute_klines', COUNT(*) FROM quant.minute_klines
UNION ALL SELECT 'quant.daily_quotes', COUNT(*) FROM quant.daily_quotes
UNION ALL SELECT 'quant.factor_values', COUNT(*) FROM quant.factor_values
UNION ALL SELECT 'quant.signals', COUNT(*) FROM quant.signals
UNION ALL SELECT 'quant.jobs', COUNT(*) FROM quant.jobs
ORDER BY table_name;

SELECT 'daily_klines_orphans' AS check_name, COUNT(*) AS failures
FROM quant.daily_klines dk
LEFT JOIN quant.stocks s ON s.symbol = dk.symbol
WHERE s.symbol IS NULL
UNION ALL
SELECT 'factor_values_orphans', COUNT(*)
FROM quant.factor_values fv
LEFT JOIN quant.stocks s ON s.symbol = fv.symbol
WHERE s.symbol IS NULL
UNION ALL
SELECT 'daily_quotes_orphans', COUNT(*)
FROM quant.daily_quotes dq
LEFT JOIN quant.stocks s ON s.symbol = dq.symbol
WHERE s.symbol IS NULL
UNION ALL
SELECT 'signals_orphans', COUNT(*)
FROM quant.signals sg
LEFT JOIN quant.stocks s ON s.symbol = sg.symbol
WHERE s.symbol IS NULL
ORDER BY check_name;

SELECT
  symbol,
  COUNT(*) AS daily_kline_rows,
  MIN(trade_date) AS first_trade_date,
  MAX(trade_date) AS last_trade_date
FROM quant.daily_klines
GROUP BY symbol
ORDER BY symbol
LIMIT 20;

SELECT
  symbol,
  COUNT(*) AS factor_rows,
  COUNT(DISTINCT factor_name) AS factor_names,
  MIN(factor_date) AS first_factor_date,
  MAX(factor_date) AS last_factor_date
FROM quant.factor_values
GROUP BY symbol
ORDER BY symbol
LIMIT 20;
