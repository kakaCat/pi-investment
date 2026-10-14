# t-821cbb 修正 test_false_success_guard 的打桩点·研发

> 需求：REQ-261003150739-b98d 修复 pytest 向真实通知渠道发消息（打桩点漂移）

## 在做什么
修正 test_false_success_guard 的打桩点·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-03T07:12:32.789Z，窗口 session-06404018-404f-4c74-b75d-0e786a1bb5d7）

研发段完成：桩目标改到 runtime 模块并写明打桩点规则。

### 完成项

- 两处桩从 alerting 改到 runtime
- 注释改写为可复用的打桩点规则

### 改动文件

- `tests/test_false_success_guard.py`

---
