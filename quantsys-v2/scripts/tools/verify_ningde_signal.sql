-- 验证宁德时代(300750)的信号是否正确

-- 1. 查看最新的CCI值
SELECT
    symbol,
    trade_date,
    close,
    volume,
    cci
FROM quant.daily_klines
WHERE symbol = '300750'
ORDER BY trade_date DESC
LIMIT 5;

-- 2. 查看生成的信号
SELECT
    symbol,
    signal_time,
    action,
    strategy,
    confidence,
    price,
    reason
FROM quant.signals
WHERE symbol = '300750'
ORDER BY signal_time DESC
LIMIT 10;

-- 3. 统计所有信号
SELECT
    action,
    COUNT(*) as count
FROM quant.signals
GROUP BY action
ORDER BY action;
