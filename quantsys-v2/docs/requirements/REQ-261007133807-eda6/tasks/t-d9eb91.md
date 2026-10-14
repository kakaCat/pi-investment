# t-d9eb91 收敛出唯一裁决出口 decide_escalation（15 条顺序表）·研发

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
收敛出唯一裁决出口 decide_escalation（15 条顺序表）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-07T10:50:08.411Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

研发段完成：顺序表与三条路径落盘，26 passed。

### 完成项

- 新增 decide_escalation（12 步顺序表）与 decide_escalation_paths（三条可信路径）
- 文案逐字沿用收敛前两处判定（兼容锁：既有 37 条用例零改动全绿）
- 首轮踩坑并修正：域 WatchRule 无 intent 字段，测试替身改为 SimpleNamespace + dict action_hint（= ORM 真实形态）
- 测试 26 passed（9 契约 + 17 裁决）

### 改动文件

- `domain/watch/services/escalation_verdict.py`
- `tests/services/test_watch_escalation_verdict.py`

### 下一步

联调段：既有 checker/disposition 回归。

---
