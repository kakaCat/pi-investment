# t-a08bf2 兼容壳：EscalationChecker.should_escalate 委托出口·联调

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
兼容壳：EscalationChecker.should_escalate 委托出口·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-07T10:55:19.267Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t4 联调段完成：engine/coordinator/包再导出三处调用方行为不变。

### 完成项

- engine 与 escalation_coordinator 仍按原签名调 should_escalate，行为不变（tests/services/test_watch_engine.py 全绿）
- instance 级阈值语义保留：EscalationChecker(anomaly_change_pct=X) 仍优先于全局缺省
- domain/watch/services/__init__.py 的再导出（EscalationChecker, QuoteData）未受影响

### 下一步

复核段：壳与出口的语义等价核对。

---
