# REQ-24e15d 批次 B3-b —— 信号测试日志落 ORM（9+2 处）

- **执行窗口**：w-32314d00（investor / 投资脑）
- **日期**：2026-09-14
- **范围**：`application/services/signal_test_log.py`（9 处）+ `experience_accumulator.py`（2 处）

---

## 1. 改动

新增：
- `models/signal_test_log.py`：**SignalTestRecord**（刻意不叫 SignalTestLog —— 后者是服务类名，
  同名会造成"到底在说服务还是说表"的混乱）
- `adapters/outbound/repositories/signal_test_log_repository.py`

服务层 `signal_test_log.py` 9 处裸 SQL 清零（含**运行时 DDL** 与三处 f-string 拼 WHERE 的聚合查询），
同时移除 `_get_conn()` / `psycopg2` / `RealDictCursor` / `_resolve_db_dsn` / `json` 五个依赖。

## 2. 一个**生产调用方**才是关键——移除私有访问器会打断它

`experience_accumulator._get_paper_stats` 与 `_get_strategy_symbol_combinations`
**也在调 `signal_log._get_conn()`**。删掉该私有访问器后它直接 `AttributeError`——
这不是测试问题，是**生产服务被打破**。所以这两处一并收口（正好也是计划里的 B3-c 内容）。

> 教训：删私有访问器前，必须 grep **整个仓库**（不只调用方模块），
> 本次是跑回归时从 `test_experience_accumulator` 的失败链里才暴露出来的。

## 3. 两个刻意保持的语义 + 一个实测坑

1. **建表时机不变**：原来每次构造服务都执行裸 `CREATE TABLE IF NOT EXISTS`；
   现走 `metadata.create_all(checkfirst=True)`，语义等价且幂等，表结构由 ORM 模型唯一确定。
2. **条件组合方式不变**：`strategy_name/action/symbol/status/日期区间` 仍是"给了才加条件"，
   且**列表查询与聚合查询共用同一套条件构造**（原代码里各写一遍，容易漂移）。
3. **坑：日期字段不能一律字符串化**。原实现用 RealDictCursor 拿到的是 `datetime.date`，
   `verify_pending` 直接对它做 `date.today() - signal_date`；我的仓储默认把日期转字符串后，
   这处算术立刻 `TypeError: unsupported operand type(s) for -: 'datetime.date' and 'str'`。
   故 `_to_dict(stringify_dates=)` 分两种口径：**内部消费方传 False**（要算术），
   API 面向调用方默认 True（要 JSON 友好）。

## 4. 验证证据（全部真库）

- **服务级 round-trip**：`record_signal`（含 details dict）→ 返回 id；
  monkeypatch 现价 11.0（入场 10.0）后 `verify_pending` → verified、win_rate 1.0、avg_pnl 10.0%、
  holding_days 30；`get_stats` / `get_records` 同步反映；`details` 原样回读 `{'k': 'v'}`；清理后 0 残留。
- **统计口径逐值核对**（合成 3 条已验证行，用完即删）：
  - A 策略 2 条（+5.0 / -3.0）→ avg 1.0、max 5.0、min -3.0、win_rate 0.5、stop_loss_rate 0.5 ✓
  - A+B 3 条 → avg 3.8333、win_rate 0.6667、stop_loss_rate 0.3333 ✓
  - 按月 → 2026-09(1 条, avg 9.5) 在 2026-08(2 条, avg 1.0) 之前（倒序）✓
  - 按策略 → A 在 B 之前（升序）✓
- **测试耦合修复**：`test_order_pnl_tracking`（8 处）/ `test_experience_accumulator`（3 处）/
  `test_daemon_pipeline`（2 处）用 `signal_log._get_conn()` 只为拿一条夹具连接 →
  改用平台的 `PooledConnection()`（语义与原先返回的完全一致）。
- **回归**：148 passed / 3 skipped / 5 failed；
  5 个失败**全部**用 HEAD worktree 复现确认既有：
  4 × `test_order_pnl_tracking`（`create_order(ds=...)` 参数漂移）+ 1 × parity 的 LLM 不可用。
- **闸门**：`--gate` 退出码 0。

## 5. 指标变化

| 指标 | B3-a2 后 | B3-b 后 | 变化 |
|---|---|---|---|
| cursor_execute | 83 | **72** | −11 |

`signal_test_log.py` 与 `experience_accumulator.py` 均 CLEAN。
