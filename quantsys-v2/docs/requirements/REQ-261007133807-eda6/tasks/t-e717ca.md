# t-e717ca 规则读接口回显「何时会叫我」·研发

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
规则读接口回显「何时会叫我」·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-07T11:12:51.339Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t11 研发段完成：读接口回显「何时会叫我」，12 passed。

### 完成项

- GET /api/watch/rules 条目追加 escalation_explain（纯读计算，不落库、不回写）
- 既有字段（含 escalation_policy）原样保留，纯追加
- 存量 NULL 策略规则说明写「未声明」，且库中仍为 NULL（用例断言读不篡改）
- 说明生成失败不得打挂列表（响亮留痕 + 字段置空）；顺带补上本文件缺失的 logger
- 新增 2 条用例（文件内共 12 passed）

### 改动文件

- `adapters/inbound/fastapi_app/routes/watch_async.py`
- `tests/adapters/test_watch_rules_api_policy.py`

### 下一步

联调段：既有 watch 路由用例回归。

---
