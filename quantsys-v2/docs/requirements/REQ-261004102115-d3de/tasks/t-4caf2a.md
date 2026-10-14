# t-4caf2a 核验迁移与兼容（管道读表切换、引用方、无新依赖）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
核验迁移与兼容（管道读表切换、引用方、无新依赖）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：analysis
- 端侧：backend

## 得到什么结果
跑：./venv/bin/python -c "from application.services.data_pipeline_service import load_trading_calendar_from_db as f;d=f('SSE');print(len(d))" → 输出 >0 且不含 trading_calendar_empty_fallback_to_klines 日志。 跑：./venv/bin/python -m pytest tests/ -q -k "trading_day or freshness" → 全过或与基线一致。 跑：git diff --stat → 不含 deployment/launchd/、不含 pyproject.toml、不含 quant.data_contracts 相关 SQL/迁移。

## 实施方案（implementation）
核验 load_trading_calendar_from_db(exchange) 从「空表回退 K 线」切换为「读表」后行为正常，回退路径与异常处理未被破坏。核验全仓 _last_trading_day 引用方（tools/health_probe.py 之外）仍可导入且语义未回归。核验未改 deployment/launchd/com.pi-investment.health-probe.plist、未改 quant.data_contracts、未新增第三方依赖。

## 上游产出摘要（dependsSummary）
- 探针接入新口径并标注判定来源
- freshness_guard 复用同一实现
- 刷新脚本改接 provider 源并一次性回填日历表

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-04T02:32:29.688Z，窗口 session-e4214a80-d4ad-4666-9705-9ee6f7921f01）

收口核验完成：日历表从空表变成管道与探针共同的真源，且改动没有溢出到调度配置、依赖清单或数据契约。

### 完成项

- 管道侧：load_trading_calendar_from_db('SSE') 返回 7791 个交易日、末日 2026-12-31，且日志中 trading_calendar_empty_fallback_to_klines 出现 0 次（不再走空表回退）。
- 引用方：application.services.scheduler_tasks_data、daily_jobs、daily_jobs_bootstrap 三个生产导入方全部 import 成功，_last_trading_day 签名未变。
- 改动面：git diff 不含 deployment/launchd/ 与 pyproject.toml；未新增第三方依赖；未改 quant.data_contracts 口径。
- 回归：pytest -k「trading_day or freshness or health_probe」92 passed（含既有守卫用例与新增回归锁）。
- 登记项：表内无任何休市日（10-01~10-07 与 09-25 均不在），主键已升为 (trade_date, exchange)。

### 下一步

全部 6 张卡完成，转入验收材料提交。

---
