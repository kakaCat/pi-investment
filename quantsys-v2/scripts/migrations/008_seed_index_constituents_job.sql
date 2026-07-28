-- 008_seed_index_constituents_job.sql
-- 注册指数成分股每日采集任务（scheduler_daemon 从该表加载）
INSERT INTO quant.scheduler_task_configs
    (task_name, description, cron_expression, command, params, is_enabled,
     executor, max_instances, misfire_grace_time, coalesce, created_by)
VALUES
    ('index_constituents_update', '指数成分股每日更新（沪深300/创业板指/科创50，csindex+sina）',
     '40 15 * * 1-5', 'infrastructure.jobs.index_constituents_update_job.execute',
     '{}'::jsonb, true, 'default', 1, 43200, true, 'migration-008')
ON CONFLICT (task_name) DO NOTHING;
