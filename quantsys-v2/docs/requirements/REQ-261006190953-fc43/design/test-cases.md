# 测试策略（REQ-261006190953-fc43）

## 1. 测试分层与文件归属（serves: FR-7）

| 层级 | 文件 | 覆盖什么 | 跑法 |
|---|---|---|---|
| 单元（写入闸门） | `tests/test_equity_snapshot_trading_day_gate.py`（**新建**） | 四条写入路径 × 交易日/周末/法定节假日/降级 的真值表；`force=True` 旁路 | `./venv/bin/python -m pytest tests/test_equity_snapshot_trading_day_gate.py -q` |
| 单元（口径） | `tests/test_nav_series.py`（**新建**） | `trading_day_set` / `filter_trading_days` / `nav_returns_from_snapshots` / `nav_coverage`；**None vs 空集口径锁** | `./venv/bin/python -m pytest tests/test_nav_series.py -q` |
| 单元（日收益与基准） | `tests/test_equity_snapshot_daily_return.py`（**既有，增量补**） | `previous_valid_snapshot` 按交易日回退；跨节假日的收益归到复市首日；`daily_return` 缺省与 NULL 语义不回归 | `./venv/bin/python -m pytest tests/test_equity_snapshot_daily_return.py -q` |
| 单元（判据不重复实现） | `tests/test_trading_day_guard.py`（**既有，只读引用**） | 判据语义由它锁；本需求不新增判据，故只要求它继续全绿 | `./venv/bin/python -m pytest tests/test_trading_day_guard.py -q` |
| 集成（任务入口） | `tests/test_daily_jobs_trading_day_gate.py`（**既有，增量补**） | `EquitySnapshotJob.run()` 在休市日返回 `skipped` 且无新行；交易日正常；`_has_bar` 不再是交易日判据 | `./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q` |
| 集成（迁移） | `tests/test_migration_purge_nontrading_snapshots.py`（**新建**，跑测试库） | dry-run 不改数据；`--apply` 后非交易日行 = 0；幂等（二次跑删 0 行）；行数异常时中止；`is_trading_day is null` 不动 | `./venv/bin/python -m pytest tests/test_migration_purge_nontrading_snapshots.py -q` |
| 跨仓（消费侧） | `agent-dh/apps/web/tests/attribution-alignment.test.ts`（**改**） | 节假日不计缺口；v2 未返 `nav_coverage` 时如实声明"未校验"、不回退 weekday | `cd ../agent-dh && npx vitest run apps/web/tests/attribution-alignment.test.ts` |
| E2E（真实台账） | 无代码：`data-model.md` §3 判据 SQL + `equity_curve` 抽查 | `2026-10-07` 无新行；`2026-10-08` 复市首日写入成功 | 见 §7 第 8 条 |

## 2. 写入闸门真值表（单元测试主表）（serves: FR-1, FR-2）

判据来源一律 `trading_day_gate.skip_non_trading_day` + `TradingDayGuard.check`；日期取**已取证的真实日历**。

| 路径（4 条） | `2026-09-30`（交易日） | `2026-09-05`（周六） | `2026-10-02`（国庆休市） | 日历降级 `degraded=True` |
|---|---|---|---|---|
| `SimulationORMRepository.upsert_equity_snapshot`（缺省） | 写入 | **拒写**（返回 None） | **拒写**（返回 None） | 写入 + 留痕 |
| `SimulationORMRepository.upsert_equity_snapshot(force=True)` | 写入 | 写入（显式旁路） | 写入（显式旁路） | 写入 |
| `DailySnapshotService.snapshot_all_accounts(target_date=…)` | `written=n, refused=0` | `written=0, refused=n` + `trading_day` 五键 | 同左 | 写入 + `degraded=True` |
| `PaperTradingEngine.take_daily_snapshot()` | 正常绩效 dict | `{'skipped': True, 'reason':…, 'trading_day_source':…}` | 同左 | 写入 + `degraded=True` |

四路径**共用同一判据**的验证方式：对每个路径打桩 `trading_day_gate.skip_non_trading_day`，
断言它**被调用过**且调用参数是目标日（防"某条路径又自己写了一套判定"）。

## 3. 读取口径测试（serves: FR-4, FR-5）

构造序列（含脏行）→ 断言：

```
输入（agent_virtual 实测同形）：
  09-04(五) 102710.39 → 09-05(六) 102908.39 → 09-06(日) 102908.39 → 09-09(三) 103445.39

期望：
  nav_returns_from_snapshots(rows, trading_days={…交易日集合…}) →
      returns 长度 = 2（09-04→09-09 一段 + 09-09 之后），且 **不含**任何"周六/周日"配对产生的收益
  同函数 trading_days=None → 退回现行行为（3 段），返回值里 verified 语义由 nav_coverage 表达
```

- `get_equity_snapshots(trading_days_only=True, limit=N)`：断言返回条数 = **交易日数**，
  且尾部日期与日历对得上（不是"取了 N 行再删几行"）。
- `previous_valid_snapshot(before=10-08, trading_days=…)` → 返回 `09-30`（不是 `10-02`）。
- **口径锁**：`trading_days=None` ⇒ `nav_coverage()['verified'] is False` 且 `missing_count == 0`
  （防"日历读失败被表达成空集合 → 序列清空 → 指标静默退化"）。
- `trading_day_set()` 在日历表为空/查询抛错时返回 **None**（不是 `set()`）。

## 4. 缺口口径测试（serves: FR-3）

| 输入（v2 `nav_coverage` 口径） | 期望 |
|---|---|
| 序列覆盖 `2026-09-30` 与 `2026-10-08`，两端齐全 | `missing_count == 0`（**10-01~10-07 不算缺口**） |
| 序列缺 `2026-09-25`（交易日） | `missing_trading_days == ['2026-09-25']`，`missing_count == 1` |
| 序列缺 `2026-09-05`（周六） | `missing_count == 0`（周末不参与） |
| 无日历（`verified=False`） | `missing_count == 0` + `basis` 明写"未做交易日校验" |

跨仓侧：`attribution-alignment.test.ts` 增两条——① `verified=true` 且缺失为空时归因**不**报缺口；
② v2 未返字段时 agent-dh 输出 `verified=false` 的"未校验"文案，**且不触发补跑建议**。

## 5. 存量清理与重算测试（serves: FR-6, FR-7）

- **dry-run 零副作用**：跑 `--dry-run` 前后比对 `quant.simulation_equity_snapshot` 行数与校验和，必须一致。
- **删除正确性**：造一个含"周六行 + 节假日行 + 交易日行 + 日历缺行(null)日期行"的小样本 →
  只有前两类被删，`null` 日期行**不动**。
- **防误删**：把待删行数改成 ≠ 实际值 → 脚本中止（非零退出）并打印差异。
- **重算一致性**：`tools/verify_equity_snapshot_consistency.py` 逐账户比对新旧
  `daily_return` / `drawdown` / `peak_value` / `max_drawdown` → 期望"独立复算零差异"。
- **幂等**：`--apply` 连跑两次，第二次删除 0 行、重算结果不变。

## 6. 负向测试（必须一并写，否则"过"没有意义）（serves: FR-1, FR-4）

1. **不许绕过判据**：四条写入路径各打桩 `skip_non_trading_day` 返回 `(True, info)`，
   断言**零 INSERT/UPDATE**（不是"返回了 skipped 但还是写了"）。
2. **不许静默降级**：日历降级时，写入返回值里必须带 `degraded=True`；接口 `nav_coverage` 必须带 `verified`。
3. **不许空集当失败**：`trading_day_set()` 失败路径断言 `is None`，
   且 `filter_trading_days(rows, None)` 返回**全量**（不是空列表）。
4. **不许 weekday 复活**：全仓 grep 断言 `simulation_repository.py` / `nav_series.py` /
   `daily_snapshot_service.py` / `RiskMetricsTool.ts` 里不出现 `weekday()` / `getUTCDay()` 形式的交易日判定。
5. **不许 force 常态化**：断言生产代码路径里 `force=True` 出现次数为 0（只允许测试与迁移脚本显式书写）。

## 7. 验收口径（可跑命令 + 期望输出）（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8）

```bash
# ① 写入闸门（四路径真值表 + 负向）
./venv/bin/python -m pytest tests/test_equity_snapshot_trading_day_gate.py -q        # 期望全过

# ② 口径单测（含 None vs 空集锁）
./venv/bin/python -m pytest tests/test_nav_series.py -q                              # 期望全过

# ③ 日收益与基准（既有文件增量）
./venv/bin/python -m pytest tests/test_equity_snapshot_daily_return.py -q            # 期望全过

# ④ 判据不回归 + 任务入口
./venv/bin/python -m pytest tests/test_trading_day_guard.py tests/test_daily_jobs_trading_day_gate.py -q

# ⑤ 迁移：dry-run 零副作用 → apply → 幂等
./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py
# 期望：打印"将删除 35 行"且不改数据
./venv/bin/python -m pytest tests/test_migration_purge_nontrading_snapshots.py -q

# ⑥ 一致性校验（逐账户零差异）
./venv/bin/python tools/verify_equity_snapshot_consistency.py \
    --accounts agent_virtual,user_main_simulation,v13_simulation,v14_simulation,v15_simulation
# 期望：每个账户 "diff=0"，退出码 0

# ⑦ 核心判据：非交易日净值行数 = 0
psql -h 127.0.0.1 -U mac -d quant_investment -c "
select count(*) from quant.simulation_equity_snapshot s
 left join quant.trading_calendar c on c.trade_date=s.snapshot_date and c.exchange='ALL'
 where c.is_trading_day is false;"                                                   # 期望 0

# ⑧ 接口口径（navPoints = 交易日数；window / nav_coverage 在场）
curl -s -X POST http://127.0.0.1:5001/api/risk/metrics -H 'Content-Type: application/json' \
  -d '{"account_name":"agent_virtual","days":20}' | python3 -m json.tool
# 期望：navPoints == window.trading_days；equity_curve（performance 接口）无周末/节假日行

# ⑨ 跨仓消费侧
cd ../agent-dh && npx vitest run apps/web/tests/attribution-alignment.test.ts          # 期望全过
```

## 8. E2E 观察（时间型，上线后回执）（serves: FR-1, FR-7）

```sql
-- 2026-10-07（国庆休市·周三）当日：期望 0 行新增
select count(*) from quant.simulation_equity_snapshot where snapshot_date = '2026-10-07';

-- 2026-10-08（复市首日）：期望 5 个账户各 1 行，且 daily_return 的基准是 09-30（不是 10-02）
select account_name, snapshot_date, daily_return from quant.simulation_equity_snapshot
 where snapshot_date = '2026-10-08' order by account_name;
```

两条判据在 10-07 / 10-08 到来前**无法预先跑**，故列为上线后回执；在此之前 §7 的 ①~⑨ 即为代码侧完成判据。
