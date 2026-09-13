-- pool_change_log.symbol 扩宽：varchar(20) → text
--
-- 背景（2026-09-13，w-32314d00，看板事件 c4cade93 / bcea3fe8）：
-- StockPoolService._log_change 写的是批量摘要 ','.join(symbols[:50])，
-- 一张 5 只票的池子 refresh 即 35 字符，超过 varchar(20) →
--   psycopg2.errors.StringDataRightTruncation: value too long for type character varying(20)
-- 变更日志整条写入失败（fail-soft 只打 warning），池操作本身不受影响但审计留痕丢失。
--
-- 幂等：重复执行无副作用。
ALTER TABLE quant.pool_change_log ALTER COLUMN symbol TYPE text;
