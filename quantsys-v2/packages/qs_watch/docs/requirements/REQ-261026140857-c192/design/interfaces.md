---
title: 账户级交易计划统一与数据库化重构 · 接口设计
status: draft
owner: PI Investment
reviewers: 用户（最终决策人）
prd: ../requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
created: 2026-10-26
updated: 2026-10-26
---

# 账户级交易计划统一与数据库化重构 · 接口设计

## 1. 通用约定

- API 前缀 `/api/plans`，单账户操作必须提供 `account` 或能由计划 ID 验证账户。
- 时间使用 ISO 8601；`trade_date` 使用 `YYYY-MM-DD`。
- 写操作必须提供 `actor`；agent 修改必须提供 `decision_audit_id`。
- 版本操作使用 `expected_version`；冲突返回 409，不产生副作用。
- 成功响应沿用 `{"success":true,"data":...}`。
- 领域失败沿用 `{"success":false,"code":"PLAN_*","error":"..."}`；`details` 可包含 item 级原因。
- readiness 检查本身成功但结果不就绪时返回 HTTP 200 + `ready=false`，不伪装成接口异常。

## 2. 核心响应对象

### 2.1 PlanItemView

```json
{
  "item_id": 101,
  "symbol": "600519.SH",
  "name": "贵州茅台",
  "action": "buy",
  "horizon": "swing",
  "target_weight": 0.1,
  "target_qty": 100,
  "thesis": "……",
  "invalidation": "……",
  "entry": {
    "combinator": "all_of",
    "valid_until": "2026-10-27T15:00:00+08:00",
    "conditions": [{"type": "price_break", "params": {"price": 1500, "direction": "above"}}]
  },
  "exit": {
    "stop_loss": {"type": "pct", "value": 8},
    "reduce_plan": [{"at_pct": 10, "sell_ratio": 0.5}]
  },
  "state": {
    "state": "ready",
    "filled_qty": 0,
    "remaining_qty": 0,
    "lock_version": 1
  },
  "legacy_plan_id": null
}
```

`conditions` 的 DSL 继续复用 WatchEngine；响应组装成兼容 agent 阅读的 entry/exit 结构，不代表数据库使用 JSON 管理核心关联。

### 2.2 ReadinessView

```json
{
  "ready": false,
  "status": "not_ready",
  "checked_at": "2026-10-26T09:20:00+08:00",
  "reasons": [
    {"code": "ENTRY_INCOMPLETE", "item_id": 101, "message": "入场条件待补"}
  ]
}
```

## 3. HTTP 接口清单

| 编号 | 方法与路径 | 语义 | 主要错误 |
|---|---|---|---|
| IF-1 | `POST /api/plans` | 手工创建账户主计划和标准化草稿 items | 400/409 |
| IF-2 | `POST /api/plans/generate` | 每日幂等生成 revision | 400/409/422 |
| IF-3 | `GET /api/plans` | 按账户列主计划，默认排除 archived/legacy | 400 |
| IF-4 | `GET /api/plans/today?account=...` | 今日 revision、items、状态和 readiness | 400 |
| IF-5 | `GET /api/plans/{plan_id}` | 主计划、版本、items、事件和迁移来源 | 404 |
| IF-6 | `PATCH /api/plans/{plan_id}` | 按 item 修改草稿并返回 diff | 400/404/409/422 |
| IF-7 | `POST /api/plans/{plan_id}/apply` | CAS 审核并冻结为 approved | 400/404/409/422 |
| IF-8 | `POST /api/plans/{plan_id}/activate` | 原子激活 approved revision | 400/404/409/422 |
| IF-9 | `GET /api/plans/{plan_id}/compile-preview` | 当前草稿与线上规则的只读 diff | 404/422 |
| IF-10 | `POST /api/plans/{plan_id}/readiness` | 执行并持久化 readiness/对账 | 404/422 |
| IF-11 | `POST /api/plans/{plan_id}/pause` | 暂停主计划和规则 | 404/422 |
| IF-12 | `POST /api/plans/{plan_id}/resume` | 恢复主计划并重新对账 | 404/409/422 |
| IF-13 | `POST /api/plans/{plan_id}/close` | 关闭主计划，持仓需处置方案 | 404/422 |
| IF-14 | `POST /api/plans/{plan_id}/archive` | 归档已关闭计划 | 404/409/422 |
| IF-15 | `GET /api/plans/{plan_id}/reflection-pack` | 当前 revision + item 材料包 | 404 |
| IF-16 | `POST /api/plans/{plan_id}/reflections` | 提交账户或 item 反思 | 400/404 |
| IF-17 | `GET /api/plans/{plan_id}/reflections` | 查询历史反思 | 404 |
| IF-18 | `GET /api/plans/{plan_id}/stats` | 按 item 聚合执行与盈亏 | 404 |
| IF-19 | `GET /api/core-plan` | deprecated 数据库兼容视图 | 400/500 |
| IF-20 | `tool: trading_plan` | agent 双端封装以上计划操作 | 透传 PLAN_* |

`POST /api/plans/from-core-plan` 不再保留；迁移完成后调用返回 404。不得新增其他文件转换端点。

## 4. 关键接口契约

### IF-1 手工创建计划

请求：

```json
{
  "account": "agent_brain",
  "name": "账户主计划",
  "actor": "user",
  "items": [
    {
      "symbol": "600519.SH",
      "action": "buy",
      "horizon": "swing",
      "target_weight": 0.1,
      "entry": {"combinator": "all_of", "conditions": []},
      "exit": {"stop_loss": {"type": "pct", "value": 8}}
    }
  ]
}
```

- 用于人工/测试创建，不是每日生成入口。
- 创建结果为主计划 + `draft` revision；不完整 item 可保存草稿但不能激活。
- 已存在当前账户主计划时返回 409 `PLAN_ALREADY_EXISTS`，不得重复创建。

### IF-2 每日生成

请求：

```json
{
  "account": "agent_brain",
  "trade_date": "2026-10-26",
  "actor": "system",
  "idempotency_key": "agent_brain:2026-10-26:generate"
}
```

- 新建返回 201；已存在同日有效 revision 返回 200 + `existing=true`。
- 返回 `plan_id/version/status/items/run_id`。
- `trade_date` 缺省只能由服务端明确取当前交易日，不能 naive 使用 UTC 日期。
- 数据过期返回 422 `PLAN_DATA_STALE`；组合决策与持仓读取失败不留下半份计划。

### IF-4 今日计划

响应核心：

```json
{
  "account": "agent_brain",
  "trade_date": "2026-10-26",
  "plan_id": 10,
  "version": 4,
  "revision_status": "active",
  "items": [],
  "market_gate": {},
  "pending_todos": 0,
  "readiness": {"ready": true, "status": "ready", "reasons": []},
  "generated_at": "2026-10-26T09:20:00+08:00"
}
```

- 无今日 revision：`plan_id=null`、`items=[]`、`ready=false`、`REVISION_MISSING`。
- 环境闸、持仓等待办数据不可用时不得用 0 或空对象冒充；对应 readiness 原因必须明确。
- `pending_todos` 不可用时保持 `null`。

### IF-6 草稿修改

请求：

```json
{
  "expected_version": 4,
  "actor": "agent",
  "decision_audit_id": "audit-123",
  "reason": "补充入场条件",
  "item_patches": [
    {
      "item_id": 101,
      "entry": {
        "combinator": "all_of",
        "conditions": [{"type": "price_break", "params": {"price": 1500, "direction": "above"}}]
      }
    }
  ]
}
```

- 只允许修改草稿/审核中 revision。
- `item_id` 不属于该计划时返回 422，不得按 symbol 自动猜测。
- 返回 `draft_version/lock_version/diff/compile_preview`，不修改线上规则。

### IF-7 APPLY 与 IF-8 ACTIVATE

APPLY：

```json
{
  "expected_version": 5,
  "actor": "agent",
  "decision_audit_id": "audit-123",
  "reason": "确认今日计划",
  "hypothesis": {"change": "补入场条件", "evidence": ["…"], "expected": "…"}
}
```

- 成功后 revision 为 `approved`，当前线上 active revision 不变。
- 重放同一 expected_version 返回 409，不重复产生版本或审计。

ACTIVATE：

```json
{"expected_version": 5, "actor": "agent", "decision_audit_id": "audit-123"}
```

- 只允许 approved revision；激活前 preflight 失败返回 422 `PLAN_NOT_READY` 和 reasons。
- 成功返回 `plan_id/version/status=active/compiled/readiness`。
- 任一规则或审计失败时全部回滚，不能返回部分 compiled 成功。

### IF-10 readiness

请求：`{"trade_date":"2026-10-26","stage":"runtime"}`。

- `stage=activation` 用于激活前校验；`runtime` 包含规则和持仓对账。
- 结果持久化并返回 `run_id/ready/reasons/checked_at`。
- 对账发现事实不自动修改成交或持仓。

### IF-11～IF-14 生命周期

- pause/resume/close 仍使用 `reason`；close 有持仓时 `close_disposition` 必填。
- pause 停用托管规则但保留映射；resume 前必须重新 readiness 和编译 diff。
- close 只关闭主计划授权，不得在无持仓处置方案时假装仓位已经消失。
- archive 要求 closed 且无反思 overdue；版本冲突返回 409。

### IF-15～IF-17 反思

提交体在现有五问基础上增加可选：

```json
{
  "plan_version": 5,
  "item_id": null,
  "answers": {"q1": "…", "q2": "…", "q3": "…", "q4": "…", "q5": "…"},
  "verdict": "keep",
  "reasoning": "……",
  "actions": [],
  "knowledge_updates": []
}
```

- 账户级 `item_id=null`；item 级必须验证属于该计划。
- `adjust/close` 的 actions 只能作为新草稿提案，不直接修改 active revision。
- 缺五问或理由返回 400 `REFLECTION_INCOMPLETE`。
- 同周期重写仍新增 reflection version，旧报告保留。

### IF-19 `/api/core-plan` 兼容接口

- 标记 `deprecated=true` 和替代接口 `/api/plans/today`。
- 数据完全来自数据库；为了旧消费者可只读映射 `holdings/execution_plan/risk_lens`。
- 不返回 `plan_file`，不检查文件存在性，不触发计划生成。
- 无计划时 `available=false`，原因来自数据库 readiness，不得读取旧文件补齐。
- 所有消费者完成迁移后再单独移除该兼容接口。

## 5. 内部事件接口

`FillEvent` 增加：

```python
plan_id: int | None
item_id: int | None
plan_version: int | None
trade_id: int | str
```

约束：

- 新计划产生的委托和成交必须同时带三个归因值。
- `PlanProgressPort` 对有计划但无 `item_id` 的新成交返回 `PLAN_ITEM_ATTRIBUTION_REQUIRED`。
- 历史旧成交只在迁移兼容读取中使用 `legacy_plan_id`，不得通用按 symbol 匹配。
- `trade_id` 是成交推进幂等键。

## 6. agent 工具契约

`trading_plan` 至少支持：

```text
today / list / get / generate / patch / apply / activate /
readiness / pause / resume / close / archive /
reflection-pack / reflect / reflections / stats
```

- `today` 是盘前第一步；`ready=false` 时 agent 不得提交新入场交易。
- patch/apply/activate 必须显式传版本；item 修改必须传 `item_id`。
- 工具透传后端错误码和 reasons，不把失败改写成“暂无计划”。
- 止损等风险退出不受新入场 readiness 禁令影响，仍走现有 agent 终判。
- agent-dh 与 agent-ts 使用同一字段和版本语义；两端契约测试使用同一组 fixture。

## 7. 错误码

| 错误码 | HTTP | 含义 |
|---|---:|---|
| `PLAN_ACCOUNT_REQUIRED` | 400 | 缺 account |
| `PLAN_SPEC_INVALID` | 400 | 计划项或条件非法 |
| `PLAN_NOT_FOUND` | 404 | 计划不存在 |
| `PLAN_ALREADY_EXISTS` | 409 | 当前账户主计划已存在 |
| `VERSION_CONFLICT` | 409 | 版本已变化，需重读 |
| `PLAN_STATE_ILLEGAL` | 422 | 生命周期迁移非法 |
| `PLAN_CHANGE_LOCKED` | 400 | 修改纪律拒绝 |
| `DECISION_AUDIT_REQUIRED` | 400 | agent 修改缺审计号 |
| `PLAN_DATA_STALE` | 422 | 行情或决策数据过期 |
| `PLAN_REVIEW_REQUIRED` | 422 | 尚未 approved |
| `PLAN_NOT_READY` | 422 | 激活/执行 preflight 失败 |
| `PLAN_ITEM_ATTRIBUTION_REQUIRED` | 422 | 新成交缺 item 归因 |
| `PLAN_RECONCILE_FAILED` | 422 | 存在未解决对账错误 |
| `PLAN_MIGRATION_REQUIRED` | 422 | 旧计划或持仓尚未完成迁移 |
| `REFLECTION_INCOMPLETE` | 400 | 反思五问或提案不完整 |

## 8. 兼容与版本策略

- 新响应字段采用 additive；但旧 `spec/targets` 不作为新接口的执行输入。
- 旧客户端在迁移期必须使用 `/api/core-plan` 只读兼容或尽快升级，不能继续调用 from-core-plan。
- API、agent 工具和数据库迁移必须按同一版本发布清单验收，避免后端已切多标而 agent 仍按单标解析。
