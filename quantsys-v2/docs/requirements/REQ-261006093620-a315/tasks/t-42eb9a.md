# t-42eb9a 执行期接门与跳过落账（含 manual 旁路）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
执行期接门与跳过落账（含 manual 旁路）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q 全过，含四条断言：休市日跳过时 _execute_command 零调用且 run.status='skipped' 且 last_error IS NULL；休市日 _report_failure_to_sink 零调用；manual=True 时照跑（status='success'）；交易日路径 complete_run_skipped 零调用。

## 实施方案（implementation）
修改 infrastructure/scheduler/job_executor.py：execute_scheduled_job(task_id, manual=False) 透传到 _execute_scheduled_job_impl(task_id, manual=manual)；在 is_enabled 检查之后、并发检查之前插入门：manual=True 直接放行；否则 policy = task.get('trading_day_policy') or 'always'、skip, info = should_skip(policy, now)，skip 为真时 create_run 后调 complete_run_skipped(run_id, result={'skipped':True,'reason':info['reason'],'trading_day_source':info['source'],'degraded':info['degraded'],'policy':policy})，打一行 info 日志并 return——不调 _execute_command、不调 _report_failure_to_sink、不发 Agent OS 事件、不写 last_error。照跑路径逐字不变（门放执行期正是 FR-7 免 reload 生效的机制）。新增 tests/infrastructure/test_scheduler_skip_ledger.py 覆盖四条负向断言。

## 上游产出摘要（dependsSummary）
- 判据真源：trading_day_gate 模块与策略入口
- 仓储层：complete_run_skipped + 抽 _finish_run

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T02:00:23.686Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

t5 完成：休市日自动到点只留 skipped、不执行不打扰，端到端实证通过。

### 完成项

- 交易日门接入执行期（并发检查之前），manual 旁路保住人工触发
- 跳过路径零副作用：不执行命令、不发通知、不写 last_error，只留一行五键 skipped
- 真端到端探针通过：真仓储 + 真门 + 真库，休市日自动到点产出 skipped（同路径此前产出 success）
- 6 条集成用例含 N1/N2/N4 三条负向断言；合并回归 81 passed未降
- 四段子卡（研发/联调/复核/测试）均已汇报并关闭

### 改动文件

- `infrastructure/scheduler/job_executor.py`
- `tests/infrastructure/test_scheduler_skip_ledger.py`
- `docs/requirements/REQ-261006093620-a315/notes/test_e2e_holiday_skip_probe.py`

### 下一步

进入 t6（t-3a7ebb）：人工触发改投一次性 manual=True job。

---
## 汇报 2（2026-10-06T02:22:06.723Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

独立复核发现 t5 的两处功能缺口（降级不留痕、跳过记账失败可外抛）已当场修复并各补一条回归锁，用例 6→8 全过。

### 完成项

- 独立复核 F5（中）已修：降级照跑时 result 并入 trading_day_gate{source,degraded,policy}，降级 warning 补上 task_id —— 原先只有跳过分支带降级痕迹，等于静默
- 独立复核 F6（中）已修：跳过分支的 create_run/complete_run_skipped 自兜底，记账失败只记 error、仍不执行命令、不外抛到调度线程
- 两条修复各补一条回归锁：test_degraded_run_annotates_result、test_skip_ledger_failure_does_not_raise
- t5 用例 6 → 8，全部通过；合并回归 81 → 83 passed
- 复核同时确认：门确实在并发检查之前（它自造「并发中存在 running run」用例证明），验收数字与我的材料一致、未发现虚报

### 改动文件

- `infrastructure/scheduler/job_executor.py`
- `tests/infrastructure/test_scheduler_skip_ledger.py`
- `docs/requirements/REQ-261006093620-a315/verification.md`

### 下一步

等人工在验收单上逐项裁决；未过项再返工。

---
