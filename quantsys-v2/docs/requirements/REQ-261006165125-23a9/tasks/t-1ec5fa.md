# t-1ec5fa 新增 tests/test_daily_jobs_quiet_noop.py（T-1~T-16 回归锁）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
新增 tests/test_daily_jobs_quiet_noop.py（T-1~T-16 回归锁）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q → 全过（≥16 passed）；并用 2>&1 | tail -3 确认 notify-guard 会话末打印 egress=0、offenders=[]（未声明的真实外发会让用例失败）。

## 实施方案（implementation）
新建 tests/test_daily_jobs_quiet_noop.py，实现 design/test-cases.md §2 的 T-1~T-16（判据白名单与反例、开关/阈值解析、宿主无事零消息而台账 success、有产出一条完成、异常 🚨、内层失败优先、人工触发回执、开关态旧行为、阈值内不发/超阈值发「⏳ 仍在运行」、阈值 0 关闭、回调异常不影响任务、trigger_job 传 manual=True）。打桩点必须是 runtime._send_feishu / runtime._mark_running / runtime._mark_done；env 用 monkeypatch.setenv；T-13 用 time.sleep(0.3) + 阈值 0.05。用例总数不超过 16 条，不做与 FR 无关扩展。

## 上游产出摘要（dependsSummary）
- runtime 接线：通知收敛 + manual 参数 + 超阈值提示 + trigger_job

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T09:09:35.107Z，窗口 session-981b7858-34a5-4ea0-88c9-a7e2efb95886）

tests-new 卡完成：本需求的回归锁落地，覆盖判据、宿主行为、回滚态与阈值提示。

### 完成项

- 新建 tests/test_daily_jobs_quiet_noop.py，T-1~T-16 十六组用例（参数化后 40 项）
- 无事零消息、有产出一条、异常 🚨、内层失败优先、人工触发回执、回滚态、阈值三态全覆盖
- 三条反向锁防止判据被悄悄放宽
- 打桩点全部落在 runtime，通知守卫 egress=0
- 合并口径 8 文件 152 passed

### 改动文件

- `tests/test_daily_jobs_quiet_noop.py`

### 下一步

rollback 卡做回滚与真实观察留痕

---
