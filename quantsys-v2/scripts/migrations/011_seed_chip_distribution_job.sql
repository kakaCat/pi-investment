-- 011_seed_chip_distribution_job.sql
-- 注册筹码分布每日增量任务（scheduler_daemon 从该表加载）
-- 排在 kline_update（40 17 * * 0-4）之后
INSERT INTO quant.scheduler_task_configs
    (task_name, description, cron_expression, command, params, is_enabled,
     executor, max_instances, misfire_grace_time, coalesce, created_by)
VALUES
    ('chip_distribution_update', '筹码分布每日增量更新（全市场成本分布+摘要指标）',
     '30 18 * * 0-4', 'infrastructure.jobs.chip_distribution_update_job.execute',
     '{}'::jsonb, true, 'default', 1, 43200, true, 'migration-011')
ON CONFLICT (task_name) DO NOTHING;
