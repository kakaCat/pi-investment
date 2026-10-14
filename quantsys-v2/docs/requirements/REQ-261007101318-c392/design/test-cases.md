# 测试用例设计（REQ-261007101318-c392）（serves: FR-1, FR-2, FR-3, FR-4）

## 0. 已实现回填说明（serves: FR-1, FR-2, FR-3, FR-4）

用户 2026-10-07 指示「你直接改，然后发送我来判断是否对」→ 代码先落地并已验证。
本文件既记录**已跑的判定标准**（含实测输出），也登记**尚未补的用例**（如实列出，不假装全覆盖）。

**实测结果（2026-10-07）**：

| 范围 | 命令 | 结果 |
|---|---|---|
| 定向（watch + notification + 审计 + ORM 漂移） | `venv/bin/python -m pytest tests/notification tests/domain/notification tests/services/test_watch_engine.py tests/services/test_watch_engine_trading_day_gate.py tests/services/test_watch_conditions.py tests/application/test_watch_disposition_engine.py tests/application/test_watch_t12_todo_creation.py tests/application/test_watch_t12_wiring.py tests/test_orm_db_drift.py -q` | **228 passed** |
| key 扫描（含 feishu/alert/circuit-breaker） | `venv/bin/python -m pytest tests -k "watch or notification or feishu or alert" -q` | **621 passed / 6143 deselected** |
| 外发守卫 | 同上（会话末打印） | `notify-guard intercepted=0 egress=0 offenders=[]`（测试零真实外发） |

## 1. FR-1 · 休市日零事件（`tests/services/test_watch_engine_trading_day_gate.py`）（serves: FR-1）

**手法**：注入 `is_trading_day_fn` + 冻结 `now_fn` —— **不依赖真实日期**（否则用例会随日历过期）。

| 用例 | 输入 | 断言 |
|---|---|---|
| `test_holiday_tick_produces_nothing_and_never_reads_rules` | 2026-10-07（周三·休市）10:00，注入 `False` | `tick() == []`；`repo.calls == 0`（**不判定**而非"判定后丢弃"）；通知器零调用 |
| `test_trading_day_in_session_still_evaluates_and_carries_level` | 2026-09-30 10:00，注入 `True` | 1 条事件；`repo.calls >= 1`；`level` 非空（**FR-4 恒下发**）；`closed_loop is False` |
| `test_trading_day_off_session_is_still_blocked` | 2026-09-30 16:00，注入 `True` | `tick() == []`；`repo.calls == 0`（时段闸门不放松） |
| `test_default_gate_knows_calendar_holiday` | 摘掉注入 → 真实 `TradingDayGuard` | `2026-10-07 → False` 且 `source` 含 `holiday`；`2026-09-30 → True` |

**未覆盖（如实登记）**：`run_forever()` 整环的日级跳过（test 里只覆盖了它调用的同一入口
`_resolve_trading_day`）。补法：以 `_stopped` 标志跑两轮 + `now_fn` 序列驱动（待补）。

## 2. FR-2/3/4 · 卡面契约（`tests/notification/test_req_c392_notification_contract.py`）（serves: FR-2, FR-3, FR-4）

| 用例 | 断言要点 |
|---|---|
| `test_card_shows_name_before_symbol` | 正文含 `佰维存储（688525）`（名称在前口径） |
| `test_missing_name_degrades_explicitly_not_to_bare_symbol` | 名称空 → 含「名称缺失」，且**不出现**臆造名称 |
| `test_notifier_never_passes_symbol_as_name` | 打桩 `_lookup_stock_name → None`：传给 facade 的 `name is None`（**不是** symbol）；`closed_loop is False` 同时下发 |
| `test_card_states_what_the_break_means_and_who_acts` | 含意图「止损盯盘」+「L1 提醒（人工判断，不唤醒 agent）」 |
| `test_entry_intent_reads_differently_from_stop_loss` | `entry` 与 `exit_stop` 正文**不同**（含「买入跟踪」/「止损盯盘」） |
| `test_closed_loop_off_promises_nothing` | `closed_loop=False` → 无「处置入口」「处置后必有回执」；`True` → 有；且两态**都有**意图与级别 |
| `test_unknown_trigger_level_hides_the_line_instead_of_guessing` | 级别空 → 不出现「**处置**：」（不臆造） |
| `test_card_carries_sender_footer` | 正文以 `—— v2-watch@test-host#4321` 结尾 |
| `test_sender_id_is_host_and_pid_scoped` | `current_sender_id()` 匹配 `v2-watch@.+?#\d+` |
| `test_legacy_path_also_marks_missing_name_and_sender` | 旧渲染（无 level）同样标「名称缺失」+ 尾注 |

## 3. FR-3 · 外发审计（`tests/notification/test_notification_audit_repository.py`）（serves: FR-3）

| 用例 | 断言要点 |
|---|---|
| `test_audit_row_records_who_sent_what` | 落一行；`title`/`content_excerpt`/`content_digest`/`delivery_channel`/`delivered`/`sender_id` 齐备 |
| `test_audit_is_upsert_not_append` | 生命周期 save 两次 → **仍只有一行**，`status` 为末态 `sent` |
| `test_audit_failure_never_breaks_notification` | 打桩内部抛错 → `save()` 返回 `False` 且**不上抛** |
| `test_service_path_stamps_channel_and_delivered_into_audit` | 走 `send_with_fallback`（agent 失败 → feishu）→ 审计记 `feishu` / `delivered=True` / `sender_id` |

## 4. 既有契约的**翻新**（本次必须改的三处，原因是它们锁的正是坏行为）（serves: FR-4）

| 文件 / 用例 | 旧断言（坏行为） | 新断言 | 为什么必须翻新 |
|---|---|---|---|
| `tests/application/test_watch_t12_todo_creation.py::test_no_todo_service_keeps_old_behavior` → 更名 `..._still_renders_level_but_promises_no_closed_loop` | `notifier.notifications == [(id, None)]`（闭环关→不给级别） | `[(id, "P1")]` + `closed_loop_flags == [False]` | 旧断言把「级别与闭环绑死」当成契约锁住；这正是 E9 的根因 |
| `tests/application/test_watch_t12_wiring.py::test_notify_level_none_when_closed_loop_off` → 更名 `..._still_computed_when_closed_loop_off` | `_notify_level(...) is None` | `== "P0"` | 同上 |
| `tests/application/test_watch_disposition_engine.py::FakeNotifier.notify` | 无 `closed_loop` 形参 → 引擎新 kwarg 触发 TypeError 被吞成"通知失败" | 接受并记录 `level`/`closed_loop` | 测试替身必须跟随被调签名 |

## 5. 判定标准（可跑，逐条对 FR）（serves: FR-1, FR-2, FR-3, FR-4）

```bash
# FR-1：休市日零事件（冻结时钟 + 注入判定，不依赖真实日期）
venv/bin/python -m pytest tests/services/test_watch_engine_trading_day_gate.py -q

# FR-2/FR-4：卡面契约（名称 / 意图 / 处置级别 / 闭环承诺门控 / 来源尾注）
venv/bin/python -m pytest tests/notification/test_req_c392_notification_contract.py -q

# FR-3：审计落库（写进去 / 幂等 / 失败不打挂 / 服务层 stamping）
venv/bin/python -m pytest tests/notification/test_notification_audit_repository.py -q

# FR-3：生产装配真的接上（打印仓储类名 + 写一条自检行 + 查回）
venv/bin/python /tmp/verify_audit_wiring.py     # 实测：NotificationAuditRepository / True / 查回成功

# 不破现状（含 ORM 漂移门——本需求未加 ORM 模型，故不引入漂移）
venv/bin/python -m pytest tests/notification tests/domain/notification \
  tests/services/test_watch_engine.py tests/services/test_watch_conditions.py \
  tests/application/test_watch_disposition_engine.py \
  tests/application/test_watch_t12_todo_creation.py tests/application/test_watch_t12_wiring.py \
  tests/test_orm_db_drift.py -q

# FR-3：上线后回执——收到卡片时能一条 SQL 回答"谁在几点发的"（时间型，10-08 复市后核对）
psql -h 127.0.0.1 -U mac -d quant_investment -c "
select occurred_at, title, delivery_channel, delivered, sender_id
  from quant.notification_audit order by occurred_at desc limit 10;"
```

## 6. 尚未补的用例（如实登记，不许当成"已覆盖"）（serves: FR-1, FR-3）

1. `run_forever()` 整环的日级跳过（见 §1「未覆盖」）。
2. `tick()` 跳过留痕的**去重**行为（同日多次调用只留一条）—— 现由 `_closed_skip_logged` 实现，无断言。
3. 异地/手工来源的**负例**：审计里查不到某张已送达卡片 → 断言"非本机所发"的判定流程
   （需飞书侧信息，属运维核对，不属单测）。
4. `notification_factory` 装配**失败**时的降级（`repository=None`）—— 有代码路径，无用例。
5. `sender_id` 的 host 段一致性（IP vs mDNS 名）—— 已知瑕疵，未纳入本次范围。

## 7. 引用规范条目（验收口径的依据，serves: FR-1, FR-2, FR-3, FR-4）

判定标准不是自拟的，逐条挂在本仓既有规范上：

| 本需求判据 | 引用的规范条目 | 出处 | 本需求实测 |
|---|---|---|---|
| 改动后相关用例必须全过 | 「All tests must pass before committing」 | 本仓 `CLAUDE.md` · Active Conventions | 定向 228 全过；key 扫描 621 全过 |
| **测试期不得真实外发**（桩必须打在被调函数所在模块；未声明外发 = 用例失败） | 「⚠️ 测试期不得真实外发通知」（`tests/notify_guard.py` + 根 `conftest.py`，默认 `fail`） | 本仓 `CLAUDE.md`；[notification-test-guard.md](../../../../architecture/notification-test-guard.md) | 会话末 `notify-guard intercepted=0 egress=0 offenders=[]` |
| 迁移必须**两个库都跑**（否则 `tests/test_orm_db_drift.py` 红）；DDL 带 `lock_timeout` | 「测试库镜像」段 + 「测试库 DDL 会被 idle in transaction 锁住」 | 本仓 `CLAUDE.md` · Database Configuration | 生产库 + `quant_test` 均 `[verify] 建表完成，当前审计行数: 0`；本需求**未加 ORM 模型**，故不引入漂移 |
| 文档与代码不得互相矛盾（发现即改） | 「失败要响亮 / 禁静默降级」 | 本仓 `CLAUDE.md` 铁律 + 节点铁律 | §6 已登记未覆盖项 5 条；本需求**不**声称全覆盖 |
| 规范档条目 C-14（提交前跑测试并与基线比对）/ C-15（改源码跑类型检查） | `reqboard_kb(kind='standard')` → `conventions.md#c-14` / `#c-15` | 知识层标准档（属 **agent-dh/DSH 仓**的构建纪律：`pnpm build`/`pnpm kb:check` 等） | **不适用于本仓**（Python 仓无 pnpm 构建门）；本仓对应口径 = pytest 全绿（上表第 1 行），已执行 |
