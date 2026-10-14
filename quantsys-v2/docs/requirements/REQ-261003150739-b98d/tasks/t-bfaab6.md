# t-bfaab6 回归锁 + 切换 fail 模式并验证回滚

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
回归锁 + 切换 fail 模式并验证回滚

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
pytest tests/test_false_success_guard.py tests/e2e/test_daily_orchestrator.py tests/test_freshness_guard.py -q → 全过且汇总 egress=0 offenders=[]；反向验证记录 ≥1 条（失败用例名 + 目标 URL）；QUANTSYS_NOTIFY_GUARD=off 重跑仍全过。

## 实施方案（implementation）
新增 tests/test_notify_guard.py 回归段（egress == 0、两个已知文件的 intercepted 计数）；默认模式切到 fail（未声明的外发 → teardown 判失败）；做一次反向验证并留证。

## 上游产出摘要（dependsSummary）
- 修正 test_false_success_guard 的打桩点
- e2e 手动触发用例不再执行真实 handler
- 新增测试期通知外发守卫（report 模式接线）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-03T07:16:06.094Z，窗口 session-06404018-404f-4c74-b75d-0e786a1bb5d7）

这一步做完，漏桩的代价从「用户收到假卡片」变成「一条红用例」：守卫默认已切到 fail 模式，反向验证确认真能抓住。

### 完成项

- 默认模式 report → fail（测试期未声明的真实外发，用例收尾即判失败）
- 新增回归锁：默认必须是 fail、本会话 egress=0、两个已知漏点的打桩点钉死
- conftest 补公开 notify_guard 句柄（设计契约）
- 反向验证：复刻旧漏点（桩打 alerting）→ 该用例失败，打出 2 次外发与目标 URL，且 egress 仍为 0
- 三文件验收命令 36 passed，汇总 intercepted=0 egress=0 offenders=[]；off 开关重跑仍全过

### 改动文件

- `tests/notify_guard.py`
- `tests/test_notify_guard.py`
- `conftest.py`

### 下一步

需求四张卡全部完成 → 提交验收材料（kind=verification）

---
## 汇报 2（2026-10-03T07:34:03.286Z，窗口 session-06404018-404f-4c74-b75d-0e786a1bb5d7）

补记：全量清点暴露了两个守卫自身的问题，已一并修掉——现在整套测试零外发、零误伤。

### 完成项

- 全量清点：守卫误伤 58 个用例（只比主机名，127.0.0.1 全中）→ 判据改为 authority（主机+端口）
- 补两条误伤回归：同主机不同端口不是接收端 / /wake 必须整段匹配
- 清出 3 个顺序相关真漏点（trading_day_guard 的降级告警 sink）→ 文件内 autouse fixture 摘掉 sink
- 最终全量清点：6154 passed / 0 failed；intercepted=0 egress=0 offenders=[]

### 改动文件

- `tests/notify_guard.py`
- `tests/test_notify_guard.py`
- `tests/test_trading_day_guard.py`

### 下一步

提交验收材料（kind=verification）

---
