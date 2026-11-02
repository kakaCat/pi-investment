# REQ-24e15d 批次 B4-b —— 熔断状态服务落 ORM（2 处）+ 一个 jsonb NULL 陷阱

- **执行窗口**：w-32314d00（investor / 投资脑）
- **日期**：2026-09-14
- **范围**：`application/services/portfolio_breaker_service.py`（2 处）

---

## 1. 改动

新增 `models/portfolio_circuit_breaker.py` + `PortfolioCircuitBreakerRepository`，
服务里两处 `db_cursor` + 裸 SQL 清零。**upsert 的 CASE/COALESCE 语义逐表达式照搬**，
fail-open 降级策略与返回形状不变。

## 2. ⚠️ 本批最有价值的发现：JSONB 列上 Python None ≠ SQL NULL

原 SQL 的 upsert 有一条刻意设计：

```sql
actions_taken = COALESCE(EXCLUDED.actions_taken, portfolio_circuit_breaker.actions_taken)
```

即"**解除熔断时传 None 不得清空上次的减仓记录**"。

我按同样表达式改写成 ORM 的 `func.coalesce(stmt.excluded.actions_taken, 旧值)`，
实测却发现 `actions_taken` 被清成了 None。

**定位**：写了一个对照探针，用**原生 SQL + NULL** 跑同一段逻辑 → 旧值 `['a']` 被正确保留。
⇒ 问题不在 COALESCE，而在 ORM 层：**JSONB 列上直接传 Python `None`，SQLAlchemy 会渲染成
JSON 字面量 `'null'::jsonb` 而不是 SQL NULL**，于是
`COALESCE('null'::jsonb, 旧值) = 'null'::jsonb` → 读回来就是 None，**静默破坏语义**。

**修法**：用 `sqlalchemy.null()` 显式表达 SQL NULL。

> 这类 bug 的可怕之处：不报错、不警告，只是把"不该丢的数据"丢了。
> 而它只会在"解除熔断"这条低频路径上体现——如果我只跑"触发熔断"的用例，永远发现不了。

## 3. 验证证据（真库 · 四条 upsert 语义逐条断言）

对照原生 SQL 的预期，全部通过：

| 语义 | 期望 | 实测 |
|---|---|---|
| `triggered_at`（解除时保留上次触发时间） | 保留 | ✅ 非空 |
| `triggered_drawdown`（COALESCE，None 不清空） | 保留 -8.5 | ✅ |
| **`actions_taken`（COALESCE，jsonb）** | **保留 ['减仓一半']** | ✅（修 null() 后） |
| `unblock_condition`（COALESCE） | 保留 | ✅ |
| `note`（**无条件覆盖**，含 NULL） | 变 None | ✅ |
| `get_status` 无记录默认值 | `{'account_name':…, 'active': False}` | ✅ |
| `is_active` fail-open | 异常 → False | ✅（结构未变） |

## 4. 回归

123 passed / 3 skipped / 2 failed / 15 errors。错误构成（按"先看第一条错"的口径拆解）：

- **1 条根因**：`psycopg2.errors.NotNullViolation: null value in column "action_type"`（既有，
  与 B4-a 记录的是同一处：`signals.action_type` 模型声明 NOT NULL 且无默认值）
- **16 条级联**：`PendingRollbackError`（scoped_session 被上一条的 aborted 事务污染）
- 2 个 failed 为既有的 `create_order(ds=...)` 参数漂移

即：**本批未引入新失败**；受影响用例单独跑均通过（`test_experience_accumulator` 6 passed）。

指标：cursor_execute 62 → **60**；`--gate` 退出码 0。
