-- stock_fund_flow.quality_flag（2026-09-13 w-c8cae280 补）
--
-- 为什么补这个迁移：生产库 quant_investment 有该列，但**仓库里没有任何迁移文件创建它** ——
-- 于是任何新建库（如测试库 quant_test）必然缺列，读取时直接报
--   psycopg2.errors.UndefinedColumn: column stock_fund_flow.quality_flag does not exist
-- 实测后果：tests/repositories/test_fund_flow_repository.py 5 个用例全红（batch_upsert 返回 0、
-- get_latest_fund_flow 取空），看起来像"资金流写不进去"，实际是测试库 schema 漂移。
--
-- 幂等：可重复执行。
ALTER TABLE quant.stock_fund_flow
    ADD COLUMN IF NOT EXISTS quality_flag varchar;

COMMENT ON COLUMN quant.stock_fund_flow.quality_flag IS
    '数据质量标记（varchar，可空）；2026-09-13 由 w-c8cae280 补迁移以消除测试库漂移';
