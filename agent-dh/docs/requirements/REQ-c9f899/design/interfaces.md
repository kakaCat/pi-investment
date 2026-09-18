# 技术设计 · 接口契约（REQ-c9f899）

## 1. HTTP 端点

### 1.1 新增：待办（闭环的唯一操作面）

| 方法 | 路径 | 请求 | 响应 | 错误 |
|------|------|------|------|------|
| GET | /api/watch/todos | level, flow_state, account, terminal, limit(默认100, 上限500) | { items:[{id,trigger_id,rule_id,symbol,account,level,flow_state,owner_kind,owner_ref,autonomy,due_at,terminal,close_reason,next_condition,action_kind,escalate_count}], total } | |
| POST | /api/watch/todos/{id}/claim | { owner_ref } | { todo } | 404 watch_todo_not_found；409 watch_todo_already_closed |
| POST | /api/watch/todos/{id}/close | { terminal, close_reason, next_condition?, action_kind, decision_audit_id? } | { todo, receipt } | 400 watch_todo_invalid_terminal；400 watch_todo_missing_audit；409 watch_todo_already_closed |

约束：terminal ∈ (handled,ignored,expired)；terminal=ignored 必须带 next_condition；action_kind ∈ (trade,rule_change) 且 flow_state=L3 时必须带 decision_audit_id。

### 1.2 新增：规则修复与抑噪

| 方法 | 路径 | 请求 | 响应 | 错误 |
|------|------|------|------|------|
| GET | /api/watch/rules/{id}/noise | - | { noise_state, suppress_until, trigger_today, trigger_days, self_heal_count, last_repair_at } | 404 |
| POST | /api/watch/rules/{id}/repair | { change_kind, params, reason, decision_audit_id? } | { rule, change } | 403 watch_rule_change_unauthorized（用户账户规则被 agent 直接改）；400 reason 必填 |

change_kind ∈ (cooldown,threshold,split,merge,retire,suppress,unsuppress)；每次调用写 quant.watch_rule_changes。

### 1.3 新增：最小观测

| 方法 | 路径 | 响应 |
|------|------|------|
| GET | /api/watch/metrics | { heartbeat_at, heartbeat_age_sec, engine_alive, pending_todos, by_level, by_flow_state, terminal_rate_today, suppressed_rules } |

### 1.4 既有端点

- 保留：/api/watch/rules（CRUD）、/api/watch/triggers（查询/stats/unresolved）、PATCH /api/watch/triggers/{id}、POST /api/watch/rules/batch。
- /api/watch/triggers/digest 保留**只读**（过渡期兼容外部脚本），不再驱动唤醒。

## 2. 领域端口（domain/watch/ports.py 扩展）

~~~
IWatchTodoRepository
  create(symbol, rule_id, trigger_id, account, level, flow_state, owner_kind, owner_ref,
         autonomy, sla_seconds, due_at, action_kind) -> Todo
  get(todo_id) -> Todo | None
  claim(todo_id, owner_ref, now) -> Todo
  close(todo_id, terminal, close_reason, next_condition, action_kind,
        decision_audit_id, closed_by, now) -> Todo
  list_overdue(now, limit) -> list[Todo]        # 巡检用：非终态且 due_at < now
  promote(todo_id, to_state, escalate_count, now) -> Todo
  list_pending(level=None, account=None, limit=...) -> list[Todo]

IWatchRuntimeStateStore
  load_all() -> dict[(rule_id,cond_idx), RuntimeRow]
  upsert_many(rows) -> None
  load_meta() / save_meta(heartbeat, current_date)

IWatchRuleChangeRepository
  record(rule_id, changed_by, change_kind, before, after, reason,
         trigger_id, todo_id, decision_audit_id) -> Change
~~~

端口实现放 adapters/outbound/repositories（ADR-001：SQL 只在适配器层）。

## 3. 唤醒载荷契约（v2 → agent-dh，POST /wake）

沿用现有协议 { event, data, timestamp }（agent-dh 的 /wake 已实现并鉴权可选）。

- event = watch_todo（新增）／ watch_digest（过渡期保留）。
- data:
  ~~~
  {
    "todo_id": 123,
    "level": "P1",
    "symbol": "601888",
    "account": "agent_brain",
    "autonomy": "autonomous",
    "sla_seconds": 1800,
    "due_at": "2026-09-18T10:00:00+08:00",
    "flow_state": "L3",
    "trigger": { "rule_id": 92, "condition": {...}, "metric": "price", "value": 53.2,
                 "trigger_price": 53.2, "triggered_at": "..." },
    "instruction": "按标的处置待处置触发；可自决时 PATCH /api/watch/todos/{id}/close ...",
    "receipt_hint": "关闭后请附 decision_audit_id"
  }
  ~~~
- 期望响应 200 {success:true}；非 200/success=false → v2 记失败并按现有重试；请求超时视为已送达（沿用现有语义，不改协议）。

## 4. 错误码汇总（新增）

| 码 | HTTP | 触发条件 |
|----|------|----------|
| watch_todo_not_found | 404 | todo 不存在 |
| watch_todo_already_closed | 409 | 已终态再次关闭 |
| watch_todo_invalid_terminal | 400 | terminal 不在枚举内 |
| watch_todo_missing_audit | 400 | L3 的 trade/rule_change 关闭缺 decision_audit_id |
| watch_todo_missing_next_condition | 400 | ignored 未给 NEXT 条件 |
| watch_rule_change_unauthorized | 403 | 用户账户规则被 agent 直接变更 |
| watch_metric_contract_violation | 500 | 判据消费侧误用 metric（响亮失败，不静默兜底） |

## 5. 兼容性

- 全部新增端点与字段为**增量**，不删既有字段；
- 旧客户端（agent-dh 现有 watch_list/watch_manage 工具）继续可用；
- 新闭环上线期间保持双写（triggers 既落库又建 todo），确认后再切收敛权威。
