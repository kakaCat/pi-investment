# 数据质量检查 — 使用指南

> 2026-10-21 重组：合并自 docs/data-quality-schedule-guide.md 与 docs/data-quality-long-term-config.md，
> 并按 2026-09-11 护栏改造（正确键名入实现）与 S9 二方包抽离（2026-10-18）后的现网实现校正。
> 旧两篇中 `runtime/` 路径、task_id 225、`scripts/init_scheduler_tasks.py --reset`、
> `python start_all.py` 等入口均已失效，本文不再保留。

## 这是什么

每日自动检查数据质量（缺失 / 重复 / 异常），可选自动补充缺失数据，产出质量报告。
两态：调度器按 `quant.scheduler_tasks` 中的任务行定时触发；也可手动执行。

## 实现位置（2026-10-18 S9 抽离后）

| 内容 | 路径 |
|---|---|
| 作业实现 | `packages/qs_ops/qs_ops/infrastructure/jobs/data_quality_check_job.py`（`DataQualityCheckJob.run()`） |
| 检查服务 | `packages/qs_ops/qs_ops/application/services/data_quality_service.py` |
| 旧路径 shim | `application/services/data_quality_service.py`（7 行 sys.modules 别名，30 天观察期后删除） |
| 任务登记 | `application/services/scheduler_tasks_registry.py` 分派调度（ADR-004：调度权在 v2 自己） |

## 任务参数（`DataQualityCheckJob.run()` 入参）

| 键 | 别名（自动兼容） | 默认 | 说明 |
|---|---|---|---|
| `check_days` | `days` | 30 | 检查最近 N 天；**上限 90**，超出自动钳制 |
| `symbols_limit` | `stock_limit` | 无（全部） | 检查股票数限制 |
| `check_all_stocks` | — | False | 置 true 时忽略 `symbols_limit`，全市场检查 |
| `auto_backfill` | — | **False** | 自动补充缺失数据 |
| `include_report` | — | False | 生成详细报告 |
| `max_runtime_sec` | — | 1800 | 墙钟预算 30 分钟 |
| `max_backfill_symbols` | — | 50 | 单次回填股票上限 |
| `quality_threshold` | — | 90.0 | 质量阈值 |

**注意**：旧文档写的 `days=730`（2 年）参数**已不再有效**——2026-09-11 起加了护栏
（`DEFAULT_CHECK_DAYS=30` / `MAX_CHECK_DAYS=90`），键名不一致或超限值会被钳制并把实效
值写进运行 notes，不再静默失效。历史事故：任务 232 曾配置 `days=365, stock_limit=100`
与实现读取的 `check_days`/`symbols_limit` 键名不一致，导致配置静默失效、实际跑
30 天 × 5699 只（run 3527 证实）。

## 手动执行

```bash
cd quantsys-v2
python -c "
from qs_ops.infrastructure.jobs.data_quality_check_job import DataQualityCheckJob

result = DataQualityCheckJob().run({
    'check_days': 30,        # 或别名 'days'：30
    'auto_backfill': True,
    'symbols_limit': 100,    # 或别名 'stock_limit'：100
    'include_report': True,
})
print(result)
"
```

## 调度接入（ADR-004 口径）

业务的定时任务由 v2 自己调度（`AGENT_OS_ENABLED=false`）。任务行在
`quant.scheduler_tasks` 表，调度与启用状态以表内为准：

```bash
# 看任务清单与最近执行
python tools/monitor_scheduler.py
python tools/monitor_scheduler.py --executions 20
# 或经 API
curl http://127.0.0.1:5001/api/scheduler/tasks | jq
curl "http://127.0.0.1:5001/api/scheduler/runs?limit=10" | jq

# 改 DB 里的任务行后必须 reload（否则旧配置仍在跑）
curl -X POST http://127.0.0.1:5001/api/scheduler/reload
```

CLAUDE.md 登记的面板口径：`data_quality_check_daily`（16:00）为在册任务之一。
新增/修改排班请走任务登记（见上表），不要往任何 YAML 或脚本里加 cron。

## 运行策略建议（基于护栏后的实测）

- 每日任务保持小窗口（30 天内）快速巡检；深度历史检查受 90 天上限约束，
  分多轮滚动执行（无害，因为 notes 留痕可核验）。
- `auto_backfill=True` 时预留预算：实测 run 3480 回填 50 只耗时 924.87s ≈ 18.5s/只；
  剩余预算不足 120s 时不会再启动回填，避免空转超时（run 3391 曾空转 2.8 小时）。
- 存量股票多时先 `symbols_limit` 限流，再放开 `check_all_stocks`。
- 每周看一眼 `scheduler_runs` 里该任务的 status 与 notes，确认钳制没有吃掉你想要的值。

## 故障排查

| 现象 | 排查 |
|---|---|
| 任务一直没跑 | `quant.scheduler_tasks` 里该任务 enabled 状态 + `POST /api/scheduler/reload`；再不行查 APSchedulerService 日志 |
| 配置了 days=365 却只跑 30 天 | 不是 bug：护栏钳制到 90；想要 90 天以上分轮次跑 |
| 配置了 stock_limit 却全市场 | 键名应为 `symbols_limit`（旧的 `stock_limit` 仍兼容，但 check_all_stocks=true 会覆盖） |
| run 超时/空转 | 缩小 `check_days` / `symbols_limit`，检查 `max_runtime_sec` |
| 质量分低于阈值无通知 | 任务内告警接线状态以代码为准；运维类告警统一走 `NotificationFacade.send_ops_*`（`FEISHU_WEBHOOK_OPS`） |

## 调度体检一句话

```bash
python tools/check_scheduler_dedup.py
```

撞点 = 0 / 每 job 每日仅 1 条 success / 单一调度入口，三条全过即健康。

---

**最后更新**：2026-10-21
