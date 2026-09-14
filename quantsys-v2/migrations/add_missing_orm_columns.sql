-- add_missing_orm_columns.sql
-- 2026-09-15（w-2129d492，chore/v2-orm-residual）
--
-- 为什么有这条迁移（模型 ↔ DDL 缺口闭合）：
--   本仓**没有迁移框架**（无 alembic、无 schema 版本表），模型与 DDL 是两份人工产物。
--   以下 9 列都被 ORM 模型声明、生产库里也**确实存在**，但**没有任何迁移创建过它们**
--   —— 它们是历次线上 ALTER 手工加上的，DDL 从未回流到本目录。
--   后果（2026-09-15 实测，不是理论风险）：测试库 quant_test 是**部分镜像**，缺这 9 列，
--   而 ORM flush 会带上模型声明的**全部**列 → 集成测试直接炸：
--       test_heatmap_repository_events 7 例 +
--       test_heatmap_service 10 例 ERROR：
--       psycopg2.errors.UndefinedColumn: column "pool_name" of relation "pool_change_log" does not exist
--   此前这些列被 tests/test_orm_db_drift.py 的 _ENV_ONLY_MISSING **豁免**掉（"测试库镜像
--   不全，非漂移"）。豁免只让门禁不报，**并没有让测试能跑** —— 豁免不是修复。
--   本迁移把 DDL 补上 → 测试库由 migrations/*.sql 重放即可收敛，豁免名单随之清空。
--
-- 幂等：全部 IF NOT EXISTS；生产库上为 no-op（列已存在）。
-- 口径：类型/可空/默认值逐列照抄生产 quant_investment 的 information_schema（2026-09-15）。

BEGIN;

-- 池变更审计：池删除后仍能凭冗余池名读回身份（R-020 数据契约明确要求）。
-- 声明处：adapters/outbound/repositories/pool_change_log_repository.py:34
ALTER TABLE quant.pool_change_log
    ADD COLUMN IF NOT EXISTS pool_name TEXT;

-- 事件日历：宏观/个股事件统一作用域（scope 决定解读口径）。
-- 声明处：adapters/outbound/repositories/event_calendar_repository.py
ALTER TABLE quant.event_calendar
    ADD COLUMN IF NOT EXISTS scope VARCHAR NOT NULL DEFAULT 'macro';
ALTER TABLE quant.event_calendar
    ADD COLUMN IF NOT EXISTS evidence_hash VARCHAR;
ALTER TABLE quant.event_calendar
    ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE quant.event_calendar
    ADD COLUMN IF NOT EXISTS symbols JSONB DEFAULT '[]'::jsonb;

-- 策略结构状态 vs 业绩状态（两条独立轴，见 strategy_list 工具的口径说明）。
-- 声明处：adapters/outbound/repositories/strategy_repository.py
ALTER TABLE quant.strategy_configs
    ADD COLUMN IF NOT EXISTS structure_status TEXT;
ALTER TABLE quant.strategy_configs
    ADD COLUMN IF NOT EXISTS performance_status TEXT;
ALTER TABLE quant.strategy_configs
    ADD COLUMN IF NOT EXISTS performance_evidence JSONB;
ALTER TABLE quant.strategy_configs
    ADD COLUMN IF NOT EXISTS performance_checked_at TIMESTAMPTZ;

COMMIT;
