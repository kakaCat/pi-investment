# t-38caaa 兼容壳：EscalationChecker.should_escalate 委托出口·复核

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
兼容壳：EscalationChecker.should_escalate 委托出口·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/REQ-261007133807-eda6/design/` 逐条核对；`npx vitest run tests/` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-07T10:55:46.284Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t4 复核段完成：壳与出口逐字段等价（含文案），壳内无判定逻辑，无偏离。

### 完成项

- 壳↔出口逐字段等价（5 例，含 reason 文本逐字一致）
- 壳内已无判定逻辑：只取实例阈值 → 委托 → 返回理由串（复核已读代码确认）
- 兼容参数 recent/concurrent 仍在签名内且不参与判定（与收敛前注释一致）
- 无偏离；依据：等价性对拍输出

### 下一步

测试段：跑既有 checker/metric 用例。

---
