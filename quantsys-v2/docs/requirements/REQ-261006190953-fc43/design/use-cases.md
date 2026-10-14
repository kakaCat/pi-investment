# 使用场景（REQ-261006190953-fc43）

每个 UC 给出：**触发 → 期望行为 → 可观察读数**。读数一律是可查的台账 / 命令 / 接口字段，不是"应该没问题"。

## UC-1 休市日：补跑落到净值写入路径（本需求的起因场景）（serves: FR-1, FR-2, FR-8）

**触发**：`2026-10-07`（国庆休市·周三）15:30，某条被 misfire 唤醒的补跑（或人工触发的 `equity_snapshot_daily`）
走到了净值快照写入。

**期望**：
1. 写入函数收到 `day=2026-10-07` → `skip_non_trading_day(day)` 返回 `(True, info)`；
2. **一行都不落库**（`quant.simulation_equity_snapshot` 无 `2026-10-07` 行）；
3. 返回值带 `{'skipped': True, 'reason': '…trading-calendar-holiday…', 'trading_day_source': 'trading-calendar-holiday'}`；
4. 日志一行 `skip_daily_write_non_trading_day`，含 `day` / `source` / `reason`。

**可观察读数**：
```sql
select count(*) from quant.simulation_equity_snapshot where snapshot_date='2026-10-07';  -- 0
```
```bash
grep -c skip_daily_write_non_trading_day logs/api.log   # ≥1
```

## UC-2 交易日：行为逐字不变（不回归）（serves: FR-1, FR-4）

**触发**：`2026-09-30`（交易日）收盘后正常快照。

**期望**：5 个账户各写 1 行；`daily_return` 基准是上一个交易日（`09-29`）而非"上一行"；
`max_drawdown` / `peak_value` 与该账户净值序列一致。

**可观察读数**：`select account_name, snapshot_date, daily_return from quant.simulation_equity_snapshot where snapshot_date='2026-09-30';`
→ 5 行、`daily_return` 非 NULL；与 `recompute_account_max_drawdown` 重算值一致。

## UC-3 日历降级：照写，但不静默（serves: FR-1, FR-8）

**触发**：日历表不可读（或解析链退回"工作日近似"）→ `TradingDayGuard.check()` 返回 `degraded=True`。

**期望**：**照写**（fail-open，宁可写一行可疑数据也不静默停摆）；
写入返回与接口 `nav_coverage` 带 `verified` / `degraded` 标记；`source` 原样透出（`unavailable` / 工作日回退源）。

**可观察读数**：`nav_coverage.verified == false` 或返回体出现 `degraded: true`；
**不得**出现"日期被判休市但 `degraded=True`"被当作正常休市跳过的情况。

## UC-4 归因/风险指标窗口：库里仍有脏行也读不到（serves: FR-4, FR-5）

**触发**：`POST /api/risk/metrics {"account_name":"agent_virtual","days":20}`（清理前的过渡期，
或回滚后库里重新出现非交易日行）。

**期望**：
1. `navPoints == window.trading_days`（都是交易日数）；
2. `window.filtered_non_trading > 0`（**兜底过滤有计数，不静默**）；
3. `equity_curve`（`/api/simulation/performance`）不含周末/节假日行；
4. 波动率 / IR / 回撤只由交易日构成。

**可观察读数**：接口返回体的 `window` 与 `nav_coverage` 两块；抽查 `equity_curve` 的日期落在日历上。

## UC-5 缺口探测：节假日不再算缺口（本需求的"补跑"根因）（serves: FR-3, FR-8）

**触发**：agent 调 `risk_metrics`，净值序列 `09-30 → 10-08`（中间整段国庆休假）。

**期望**：
1. v2 返回 `nav_coverage.missing_count == 0`；
2. agent-dh 原样透出，文案用"交易日"；
3. **不出现**"缺口已补跑"这类由假日伪缺口逼出来的动作。

**可观察读数**：`nav_coverage.missing_trading_days == []`；
构造缺 `2026-09-25`（真交易日）时 `missing_count == 1`——证明这项**是活的**，不是常驻 0 噪声。

## UC-6 存量清理：35 行删除 + 派生链重算（serves: FR-6, FR-7）

**触发**：人工执行 `20261006_purge_nontrading_equity_snapshots.py --apply`。

**期望**：
1. 备份表 `quant.bak_equity_snapshot_nontrading_w_0a409569` 先有 35 行（含 `deleted_reason`）；
2. 主表删除 35 行；§7 判据 SQL 返回 0；
3. 受影响账户的 `daily_return` / `drawdown` / `peak_value` / `max_drawdown` 重算后与独立复算零差异；
4. 脚本回执逐账户打印"删除 N 行 / 重算 M 行 / 差异 0"。

**可观察读数**：`tools/verify_equity_snapshot_consistency.py` 退出码 0（每账户 `diff=0`）。

## UC-7 回滚：从备份表恢复（serves: FR-6, FR-7）

**触发**：清理后发现某账户历史口径需要保留 → `… --rollback`。

**期望**：
1. 备份行按 `(account_name, snapshot_date)` 回插，冲突则跳过（幂等）；
2. 脚本**响亮打印**「正在恢复 N 行非交易日净值行——这是回滚动作，不是正常写入」；
3. 回插后重跑重算，指标回到清理前口径。

**可观察读数**：回插后行数恢复 + 一致性校验零差异；日志含上述告警句。

## UC-8 复市首日：不得被跳过（serves: FR-1, FR-5）

**触发**：`2026-10-08`（复市首日）收盘后快照。

**期望**：正常写入；`daily_return` 的基准是 `2026-09-30`（**跨过整段假期**），
而不是 `2026-10-02`（被删掉的假日假快照）。

**可观察读数**：`select daily_return from quant.simulation_equity_snapshot where account_name='agent_virtual' and snapshot_date='2026-10-08';`
→ 该值等于 `total_value(10-08)/total_value(09-30)-1`（扣除外部入金）。

## UC-9 运维/测试：显式强制写入（serves: FR-1, FR-6）

**触发**：测试构造历史序列，或运维需要复原某行 → `upsert_equity_snapshot(..., force=True)`。

**期望**：写入成功，但**调用点必须显式书写 force 并写明理由**；生产代码路径中 `force=True` 出现次数为 0。

**可观察读数**：`grep -rn "force=True" application/ adapters/ | grep -v test` → 空（迁移脚本内的显式 SQL 不在此列）。
