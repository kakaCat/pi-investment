# t-b3dcd8 落库两列 + 通知变量透传·研发

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
落库两列 + 通知变量透传·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-07T11:12:51.011Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t8 研发段完成：码与理由全链透传并落库，6 条用例通过。

### 完成项

- 链路：engine → notifier.notify(escalation_code) → _record → 仓储两列；同时透传到通知变量
- dto.TriggerPayload 增 escalation_code 并写入 variables；facade 两处 vars 同步下发（含 L2 target-agent 分支）
- 六条用例：去重短路落库带码 / 正常路径落库+变量带码 / 写库失败不阻断通知（stdout 留痕）/ 真库 deduped 与 auto_observed 行码非 NULL / 不传码为 NULL
- 修了两处真实缺陷：① facade 的 _send_l2_via_target_agent 漏签名（NameError，被通知测试抓到）；② 测试替身 FakeNotifier 签名未跟进（异常被当通知失败吞掉 → 调用列表空）
- 如实声明：替身签名跟进属测试侧改动（断言内容未变），非行为变更

### 改动文件

- `application/services/watch_engine/notifier.py`
- `application/services/watch_engine/dto.py`
- `application/notification/notification_facade.py`
- `adapters/outbound/repositories/watch_rule_repository.py`
- `application/services/watch_engine/engine.py`
- `tests/services/test_watch_trigger_escalation_columns.py`
- `tests/application/test_watch_disposition_engine.py`

### 下一步

联调段：相关全套回归。

---
