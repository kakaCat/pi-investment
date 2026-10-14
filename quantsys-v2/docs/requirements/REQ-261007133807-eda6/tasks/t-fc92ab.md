# t-fc92ab 落库两列 + 通知变量透传

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
落库两列 + 通知变量透传

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/services/test_watch_trigger_escalation_columns.py -q 全绿；断言 deduped 与 auto_observed 两种处置的行 escalation_code 非 NULL；模拟写库异常时通知仍发出且日志含 error。

## 实施方案（implementation）
adapters/outbound/repositories/watch_rule_repository.py 的 WatchTriggerRepository.record 增 escalation_code / escalation_reason 两参数；application/services/watch_engine/notifier.py 的 _record 写入两列、TriggerPayload 增 escalation_code；application/services/watch_engine/dto.py 与 application/notification/notification_facade.py 把 escalation_code 透传进通知变量。写库失败只留痕不阻断。

## 上游产出摘要（dependsSummary）
- tick() 单链路接线（裁决 → 处置 → 去重覆盖 → 通知）
- 迁移：watch_triggers 加两列（两个库都跑）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-07T11:13:57.447Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t8 完成：裁决码落库与变量透传，四段子卡全绿。

### 完成项

- 码与理由全链透传（engine → notifier → dto/facade → 仓储两列）并写入通知变量
- 真库验证：deduped 与 auto_observed 两种处置的行码非 NULL；不传码才落 NULL
- 写库失败不阻断通知（stdout 留痕）；6 条用例 + 相关 49 / 全 watch 261 passed
- 修复两处真实缺陷：facade L2 分支漏签名、测试替身签名未跟进（后者属测试侧，断言未变）

### 改动文件

- `application/services/watch_engine/notifier.py`
- `application/services/watch_engine/dto.py`
- `application/notification/notification_facade.py`
- `adapters/outbound/repositories/watch_rule_repository.py`
- `application/services/watch_engine/engine.py`
- `tests/services/test_watch_trigger_escalation_columns.py`
- `tests/application/test_watch_disposition_engine.py`

### 下一步

t13 端到端验收汇总。

---
