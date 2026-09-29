# t-db1d48 先定契约：挂起确认能标出「被中止」，判定口径只留一处·测试

> 需求：REQ-260927123256-196b pm 确认弹框改为真正阻塞（与原生 ask_user_question 等待语义对齐）

## 在做什么
先定契约：挂起确认能标出「被中止」，判定口径只留一处·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
目标命令输出全绿（贴命令与结果摘要）

---
## 汇报 1（2026-09-27T05:43:46.371Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

测试子卡完成：验收命令 pending-guard.test.ts 9/9 全绿，回归 ask-confirm-pending 11/11；三条验收断言（plan/artifact 落章判定、markInterrupted 幂等、createdAt 早于中止不提前过期）逐条有覆盖。测试证据见 docs/requirements/REQ-260927123256-196b/evidence/t-db1d48-test.md。

### 完成项

- 验收命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts → 9 passed / 0 failed（exit 0）
- 回归：pending-guard + ask-confirm-pending → 20 passed（2 files）
- 断言 1：targetConfirmedInLedger 对 plan/artifact 落章 true、未落章 false
- 断言 2：markInterrupted 二次调用 interruptedAt 不变；未知 ticket 不抛
- 断言 3：过期基准 (interruptedAt ?? createdAt)+ttl，createdAt 早于中止不提前失效
- 测试证据文档已落盘（含命令与输出摘要）

### 改动文件

- `docs/requirements/REQ-260927123256-196b/evidence/t-db1d48-test.md`
- `packages/web/dsh-pmboard/tests/pending-guard.test.ts`

### 下一步

父卡 t-f8ed18 收尾：四张子卡全部完成，父卡可进 done。

---
