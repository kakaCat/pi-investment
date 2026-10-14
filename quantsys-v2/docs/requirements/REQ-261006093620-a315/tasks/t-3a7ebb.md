# t-3a7ebb 人工触发改投一次性 manual=True job

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
人工触发改投一次性 manual=True job

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/infrastructure/test_apscheduler_service.py -q 全过；断言 scheduler.get_job('task_1').next_run_time 与触发前相等（不再被人工触发扰动），且 get_jobs() 中出现 manual_1_* 一次性 job 且其 kwargs['manual'] is True。

## 实施方案（implementation）
修改 infrastructure/scheduler/apscheduler_service.py 的 trigger_task_now：保留 job 不存在时抛 ValueError 的既有语义；把 modify_job(next_run_time=now) 换成 add_job(func=execute_scheduled_job, trigger=DateTrigger(run_date=datetime.now()), args=[task_id], kwargs={'manual': True}, id=f'manual_{task_id}_{int(time.time())}', name=f'[manual] {job.name}', replace_existing=False, misfire_grace_time=None)。同步修改 tests/infrastructure/test_apscheduler_service.py 的 test_trigger_task_now 断言。路由层不做改动。

## 上游产出摘要（dependsSummary）
- 执行期接门与跳过落账（含 manual 旁路）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T02:01:48.468Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

t6 完成：人工触发与自动到点在同一执行体上可区分，且不再扰动 cron 排期。

### 完成项

- 人工触发改为投递一次性 manual=True job，保住 FR-6 的人工口子
- 不再扰动 cron 的 next_run_time（旧实现会提前排期、可能吞掉当天正常排班）
- 保留 job 不存在抛 ValueError 的既有语义，路由层与 legacy 降级路径零改动
- 13 条该文件用例 + 合并回归 81 条全过
- 复核中一处口径不严已自我更正并落卡（docstring 提及被误计为调用点）
- 四段子卡（研发/联调/复核/测试）均已汇报并关闭

### 改动文件

- `infrastructure/scheduler/apscheduler_service.py`
- `tests/infrastructure/test_apscheduler_service.py`

### 下一步

进入 t7（t-54d79f）：巡检口径同步 should_have_run 与 watchdog。

---
