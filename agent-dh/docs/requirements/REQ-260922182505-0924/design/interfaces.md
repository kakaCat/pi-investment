---
requirement_refs: BUG-1
---

# 接口设计 · REQ-260922182505-0924

## 删除的 HTTP 端点 `serves: BUG-1`

GET /dashboard/api/reqboard/triage、POST triage/confirm、triage/rebind、triage/reject——删除后返回既有的"未知路由"404 信封（not_found），无新错误码。前端 fetchTriage/triageConfirm/triageRebind/triageReject 同步删除。

## 删除的内部函数 `serves: BUG-1`

window.ts `hasPendingSuggestion(ledger, windowKey)` 与 `pendingSuggestionFor(...)`；support.ts `findPending(...)`；Predicates `isPendingTriage/isResolvedTriage`。capture/create 工具的行为变化：前置拒绝码 `REQBOARD_PENDING_TRIAGE` 不再可能触发（无生产端）；schema 与返回体结构不变。

## 保留冻结的契约 `serves: BUG-1`

`ReqboardLedger.triages: TriageRecord[]`、`TriageRecord` 类型、JsonLedgerRepository 的 load/mutate 管道——一字不动。
