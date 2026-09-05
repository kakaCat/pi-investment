-- ============================================================
-- 2026-09-05 signal_tracking 迁移 public → quant（w-8366e526）
-- 审计 E-6：signal_tracking 落在 public（legacy 遗留 schema），quantsys-v2 全部
-- 读写代码均用未限定表名（默认 search_path=public 碰巧可用）；后续任何 session
-- search_path 变更即断。收敛到业务 schema quant，与 quant.signal_* 家族对齐。
--
-- 已在生产库执行（idempotent 重跑安全）：
--   1) 删除测试污染行（source LIKE 'test%'，9 行：test_attribution/test_suite/
--      test_client/test_integration/test_duplicate），保留 9 行真实信号
--   2) ALTER TABLE public.signal_tracking SET SCHEMA quant
--      （owned 序列 quant.signal_tracking_id_seq 随表自动迁移）
--   3) id 默认值改为显式限定 nextval('quant.signal_tracking_id_seq')，
--      防未限定 regclass 依赖 search_path 失效
-- 配套代码：repository / attribution_service / weekly_report_service 全部 SQL
-- 限定 quant.signal_tracking。
-- ============================================================

-- 1) 清测试污染（可重复执行：已删则 0 行）
DELETE FROM public.signal_tracking WHERE source LIKE 'test%';

-- 2) 表迁 quant（owned 序列自动随迁）
ALTER TABLE public.signal_tracking SET SCHEMA quant;

-- 3) id 默认值显式限定 schema
ALTER TABLE quant.signal_tracking
    ALTER COLUMN id SET DEFAULT nextval('quant.signal_tracking_id_seq'::regclass);

-- 验证
-- SELECT tablename FROM pg_tables WHERE schemaname='quant' AND tablename='signal_tracking';
-- SELECT source, count(*) FROM quant.signal_tracking GROUP BY source;
-- SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename='signal_tracking';  -- 0
