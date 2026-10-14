# t-53b2de 落码表与裁决结果契约（EscalationCode + Verdict）·复核

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
落码表与裁决结果契约（EscalationCode + Verdict）·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/REQ-261007133807-eda6/design/` 逐条核对；`npx vitest run tests/` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-07T10:47:24.004Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

复核段完成：码表与设计文档逐行对拍一致（15/15，叫与不叫集合一致）。

### 完成项

- 设计文档 data-model.md 码表 15 行 vs 代码 EscalationCode.ALL：码集合一致、叫/不叫集合一致
- 发现并修正复核脚本自身的缺陷：正则 [A-Z_]+ 漏了带数字的码（RULE_LEVEL_L2）
- 给 t12 的提醒：正式 parity 测试的正则必须容忍数字（[A-Z0-9_]+）
- 与设计 §关键决策 2 核对：命中路径未单开列，由码表派生，一致

### 下一步

测试段：跑 -k code_table 验收命令。

---
