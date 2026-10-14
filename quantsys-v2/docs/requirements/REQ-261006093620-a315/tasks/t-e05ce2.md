# t-e05ce2 数据契约：三值列 + CHECK + 8 行回填 + ORM

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
数据契约：三值列 + CHECK + 8 行回填 + ORM

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
迁移脚本不带 --apply 时退出码 0 且只打印 DDL；--apply --dsn postgresql://mac@127.0.0.1:5432/quant_test 后 psql -d quant_test -c "\d quant.scheduler_tasks" 出现 trading_day_policy 列；./venv/bin/python -m pytest tests/test_orm_db_drift.py -q 全过；数据断言：232 行为 holidays、其余 7 行为 trading-days，且其余启用行均为 always。

## 实施方案（implementation）
新建 infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py：ADD COLUMN IF NOT EXISTS trading_day_policy varchar(16) NOT NULL DEFAULT 'always' 并加 CHECK (trading_day_policy IN ('always','trading-days','holidays'))；按 id 精确回填 8 行（250/247/242/259/249/261/237 = 'trading-days'；232 = 'holidays'），每行 rowcount=0 只打印警告不失败；沿用 20261002 迁移约定：缺省 dry-run 只打印、--apply 才写、加 lock_timeout、verify 段防空表（避免 row[0] 在空表 TypeError）。修改 infrastructure/persistence/orm/models/scheduler.py 的 SchedulerTaskConfig 加同名列（String(16), nullable=False, server_default='always'）。生产库与测试库都必须 apply（显式 --dsn），否则 test_orm_db_drift.py 红。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T01:54:43.696Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

t2 数据契约完成：三值列 + CHECK + 8 行回填 + ORM 同批落地，两库均已 apply，边界与幂等已实证。

### 完成项

- 云迁移与 ORM 同批落地（迁移脚本 + SchedulerTaskConfig 新列）
- 两个库都已 apply：测试库走空表路径、生产库 8 行精确回填
- 数据断言：挂门 7 行 trading-days + 1 行 holidays（232），其余启用行全为 always
- CHECK 边界实证：非法值被拦住；迁移幂等：重跑零写入
- ORM 漂移门 6 passed；调度侧回归基线 67 passed 未降
- 四段子卡（研发/联调/复核/测试）均已汇报并关闭

### 改动文件

- `infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py`
- `infrastructure/persistence/orm/models/scheduler.py`

### 下一步

进入 t3（t-d91b87）：③ 退为薄转发 + 打桩点迁移。

---
