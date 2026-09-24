---
requirement_refs: BUG-1, BUG-2
---

# 测试用例 · REQ-260922182505-0924

## 删除同步（随删随改） `serves: BUG-1`

TC-1 api-client.test.ts 删 fetchTriage/triage* 用例；TC-2 capture.test.ts/capture-hook.test.ts 的 hasPendingSuggestion 分支改为只覆盖 bound/unbound；TC-3 reqboard.test.ts 删 triage 路由用例；TC-4 其余引用文件（token-endpoint/ledger-v6-token/prompt-cost/progress-nodes-fallback/timeline/repository/harness/tools-schema）按编译/测试报错逐个同步。migration.test.ts 的 v4 fixture（含 triages）**不动**——它就是"老台账照常加载"的锁定证据。

## 验收实证 `serves: BUG-1, BUG-2`

TC-5 `grep -rn "triage" src/ --include="*.ts"` 只剩 protocol.ts 冻结契约 + JsonLedgerRepository 管道 + rollup 读取 + 历史注释；TC-6 部署后 `curl /dashboard/api/reqboard/triage` 返回 not_found；TC-7 看板打开正常渲染、无 triage 视图入口；TC-8 全量回归失败集与主干基线差集为空；TC-9 `ls src/application/internal/*.bak*` 为空。
