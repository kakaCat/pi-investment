# 拆分计划（REQ-261006190953-fc43）

## 1. 目标（一段人能读懂的）

把"净值序列 = 哪些日期算数"收成**交易日历唯一口径**：非交易日的行**写不进去**（写入闸门）、
**读不到**（读取端兜底过滤）、**不算缺口**（缺口判断从 agent-dh 搬到持有日历的 v2）；
并清掉已落库的 35 行脏数据、重算派生字段，最后留一条常驻巡检判据证明"库里没有非交易日净值行"。

## 2. 改动盘点（按设计逐份对照）

**新增（6 个文件）**

| 路径 | 职责 |
|---|---|
| `application/services/nav_series.py` | 净值序列口径唯一实现（交易日集合 / 过滤 / 日收益 / 缺口） |
| `infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py` | 备份 → 删 35 行 → 全序列重算（dry-run / apply / rollback） |
| `tools/verify_equity_snapshot_consistency.py` | 逐账户比对重算结果（零差异判据） |
| `tools/check_nontrading_equity_snapshots.py` | 常驻巡检：非交易日净值行数，退出码 0/2/3 |
| `tests/test_nav_series.py` | 口径单测（含 None-vs-空集锁） |
| `tests/test_equity_snapshot_trading_day_gate.py` | 写入闸门四路径真值表 |
| `tests/test_risk_metrics_nav_window.py` | 两个 HTTP 接口的 window / nav_coverage 契约 |
| `tests/test_migration_purge_nontrading_snapshots.py` | 迁移 dry-run / 幂等 / 防误删 |
| `tests/test_check_nontrading_equity_snapshots.py` | 巡检器活性（造脏行必须报 2） |

**修改（8 个文件）**

| 路径 | 改什么 |
|---|---|
| `adapters/outbound/repositories/simulation_repository.py` | `upsert_equity_snapshot` 加唯一写入闸门（+`force`）；`get_equity_snapshots` 支持只取交易日；`previous_valid_snapshot` 基准按交易日回退 |
| `application/services/risk_metrics_service.py` | `nav_returns_from_snapshots` 收敛为对 `nav_series` 的薄转发 shim（导入路径不破） |
| `application/services/evolution/daily_snapshot_service.py` | `snapshot_all_accounts` 返回 `refused`；`EquitySnapshotJob` 的 `_has_bar` 降级为"是否已收盘"辅助判据 |
| `application/trading/paper_trading_engine.py` | `take_daily_snapshot` 处理闸门拒写（snap=None），返回结构化 `skipped` |
| `adapters/inbound/fastapi_app/routes/analysis_async.py` | `/api/risk/metrics`：`days` = 交易日数，响应加 `window` / `nav_coverage` |
| `adapters/inbound/fastapi_app/routes/simulation_async.py` | `/api/simulation/performance`：`equity_curve` 只含交易日，响应加 `window` / `nav_coverage` |
| `application/services/trading_day_guard.py` | **只改模块 docstring**：删掉失真的「已标记 `is_synthetic=true` 并从统计口径排除」（该列与代码均不存在） |
| `agent-dh/packages/tools/risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts` + `prompt.ts`（跨仓，2 个文件） | `probeNavCoverage` 改为**消费** v2 的 `nav_coverage`，不再自算缺口 |
| `agent-dh/apps/web/tests/attribution-alignment.test.ts`（跨仓） | 锁"节假日不计缺口""缺字段时如实声明未校验" |
| `tests/test_equity_snapshot_daily_return.py`（改） | `previous_valid_snapshot` 交易日回退的增量用例 |
| `tests/test_daily_jobs_trading_day_gate.py`（改） | `EquitySnapshotJob` 休市日 `skipped` 的增量用例 |

**删除**：无（本需求不删任何符号；35 行脏数据是**数据**删除，不是代码删除，且有备份表）。

## 3. 任务表

口径：`DU = files×1 + anchors×0.5 + chars/2000`，容量 16 DU/卡。

| key | 标题 | phase | side | depends_on | FR | files | anchors | chars | DU | 关联 D-x |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 落 `nav_series` 口径模块与契约（shim 保兼容） | implement | backend | — | FR-4, FR-5, FR-7 | 3 | 8 | 1100 | 7.55 | D-1, D-5 |
| B | 净值仓储加唯一写入闸门 + 交易日回退基准 | implement | backend | — | FR-1, FR-2, FR-4, FR-5 | 3 | 8 | 1300 | 7.65 | D-1, D-3 |
| C | 写入入口接线：拒写留痕（两处服务 + 任务） | implement | backend | B | FR-1, FR-2, FR-8 | 4 | 6 | 1200 | 7.60 | D-3 |
| D | 读取端接线：`days`=交易日数 + window / nav_coverage | implement | backend | A, B | FR-4, FR-7, FR-8 | 3 | 7 | 1200 | 7.10 | D-3, D-5 |
| F | 存量清理迁移 + 一致性校验（含回滚） | implement | backend | B | FR-6, FR-7 | 3 | 8 | 1500 | 7.75 | D-4 |
| G | 常驻巡检判据 + 纠正失真的 `is_synthetic` 注释 | implement | backend | B | FR-7, FR-8 | 3 | 5 | 1000 | 6.00 | D-4 |
| E | 跨仓消费侧：agent-dh 改读 v2 缺口口径 | implement | backend | D | FR-3, FR-8 | 3 | 5 | 1000 | 6.00 | D-3 |

**超容量卡：无**（最大 7.75 DU < 容量 16）。

### 覆盖对照表（需求条款 ↔ 计划 key）

| FR | 承接卡 | 判据落点 |
|---|---|---|
| FR-1 写入闸门 | B、C | B：仓储拒写；C：两处服务 `refused`/`skipped` |
| FR-2 门设在被调函数层 | B、C | C 打桩断言两路径都调 `skip_non_trading_day` |
| FR-3 缺口改交易日口径 | E（口径由 D 提供） | E：节假日不计缺口 + 缺字段如实声明 |
| FR-4 读取端按交易日取数 | A、B、D | A：纯函数；B：`trading_days_only`；D：接口 |
| FR-5 基准取上一交易日 | A、B | B：`previous_valid_snapshot` 回退到 09-30 |
| FR-6 存量清理 + 重算 | F | F：删除 + 全序列重放 + 一致性 |
| FR-7 清理可证伪 + 常驻判据 | A、D、F、G | G：巡检器退出码；F：迁移后行数 0 |
| FR-8 口径可见化 | C、D、E、G | D：`window`/`nav_coverage`；E：文案 |

## 4. 每卡的实施与验收（摘要；验收均可跑）

### A · `nav_series` 口径模块
**实施**：新建 `application/services/nav_series.py`（`trading_day_set` / `filter_trading_days` /
`nav_returns_from_snapshots` / `nav_coverage`，签名见 `design/interfaces.md` §2）；
`application/services/risk_metrics_service.py` 的同名函数改为转发 shim；
新增 `tests/test_nav_series.py`。
**验收**：`./venv/bin/python -m pytest tests/test_nav_series.py -q` 全过，且其中断言
① `trading_day_set()` 失败返回 `None`（不是 `set()`）；② `filter_trading_days(rows, None)` 返回全量；
③ 含周末行的序列经过滤后收益条数 = 交易日数 − 1；④ 跨假日涨跌归到复市首日一段；
⑤ 覆盖 `09-30→10-08` 时 `missing_count == 0`；⑥ 缺 `2026-09-25` 时 `missing_count == 1`；
⑦ `trading_days=None` ⇒ `verified is False` 且 `missing_count == 0`；⑧ `from application.services.risk_metrics_service import nav_returns_from_snapshots` 仍可用。

### B · 仓储闸门 + 交易日回退
**实施**：改 `adapters/outbound/repositories/simulation_repository.py`：
`upsert_equity_snapshot` 调 `trading_day_gate.skip_non_trading_day(day)` 决定是否落库（+`force` 旁路）；
`get_equity_snapshots` 加 `trading_days_only` / `trading_days`（先全取→过滤→取尾 `limit`）；
`previous_valid_snapshot` 加 `trading_days` 回退；`calculate_daily_return` 走新基准。
新建 `tests/test_equity_snapshot_trading_day_gate.py`（仓储路径部分），
改 `tests/test_equity_snapshot_daily_return.py`。
**验收**：`./venv/bin/python -m pytest tests/test_equity_snapshot_trading_day_gate.py tests/test_equity_snapshot_daily_return.py -q` 全过，
且断言 ① 休市日 upsert 返回 `None` 且该日**零行**；② 交易日正常落库；③ 降级日照写且带 `degraded`；
④ `force=True` 可写（显式旁路）；⑤ `trading_days_only=True, limit=N` 返回**交易日数 = N**；
⑥ `trading_days=None` 时不过滤；⑦ `previous_valid_snapshot(before=10-08)` 返回 `09-30` 而非 `10-02`；
⑧ 残缺快照（`total_value<cash`）仍被跳过。

### C · 写入入口接线
**实施**：改 `application/services/evolution/daily_snapshot_service.py`（`snapshot_all_accounts` 汇总 `refused`
与 `trading_day`；`EquitySnapshotJob._has_bar` 降级为"是否已收盘"辅助判据）；
改 `application/trading/paper_trading_engine.py`（`take_daily_snapshot` 处理 `snap is None` → 返回
`{'skipped': True, 'reason':…, 'trading_day_source':…}`）；改 `tests/test_daily_jobs_trading_day_gate.py`；
扩展 `tests/test_equity_snapshot_trading_day_gate.py` 的服务路径部分。
**验收**：`./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_equity_snapshot_trading_day_gate.py -q` 全过，
断言 ① 休市日 `snapshot_all_accounts` → `written=0, refused=n` 且带五键 `trading_day`；
② 交易日 `written=n, refused=0`；③ `take_daily_snapshot` 休市日返回 `skipped` 且**不抛 AttributeError**；
④ `EquitySnapshotJob.run` 休市日 `skipped=True` 且 `reason` 区分"非交易日"与"未收盘"；
⑤ **K 线存在但日历判休市**时仍跳过（`_has_bar` 不再是交易日判据）；
⑥ 打桩 `skip_non_trading_day` 断言两条路径**都**调用了它。

### D · 读取端接线
**实施**：改 `adapters/inbound/fastapi_app/routes/analysis_async.py`（`/api/risk/metrics`：
`days` 传为交易日数、响应加 `window` 与 `nav_coverage`）；
改 `adapters/inbound/fastapi_app/routes/simulation_async.py`（`/api/simulation/performance`：
`equity_curve` 只含交易日、响应加同两块）；新建 `tests/test_risk_metrics_nav_window.py`。
**验收**：`./venv/bin/python -m pytest tests/test_risk_metrics_nav_window.py -q` 全过，
断言 ① `navPoints == window.trading_days`；② `window` 五字段齐（`from/to/trading_days/filtered_non_trading/trading_day_source`）；
③ `nav_coverage.verified` 在场；④ 造脏行时 `equity_curve` 无该行且 `filtered_non_trading > 0`；
⑤ `nav_coverage` **只报净值缺口**、不含基准缺口（D-5）；⑥ `max_drawdown` 取自重算后的账户字段；
⑦ 既有键（`returnsSource`/`sharpeRatio`/…）一个不缺（回归）。

### F · 存量清理迁移 + 一致性校验
**实施**：新建 `infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py`
（dry-run 缺省；`--apply`；`--rollback`；备份表 `quant.bak_equity_snapshot_nontrading_w_0a409569`；
`lock_timeout=30s`）；新建 `tools/verify_equity_snapshot_consistency.py`；
新建 `tests/test_migration_purge_nontrading_snapshots.py`（跑测试库）。
**验收**：`./venv/bin/python -m pytest tests/test_migration_purge_nontrading_snapshots.py -q` 全过，且
① dry-run 前后表行数与校验和一致；② 删除只命中 `is_trading_day is false`，`null` 日期行**不动**；
③ 待删行数 ≠ 35 时脚本**非零退出**并打印差异；④ 备份行数 ≥ 待删行数，否则中止；
⑤ `--apply` 后判据 SQL（非交易日行数）为 0；⑥ 重算后 `tools/verify_equity_snapshot_consistency.py` 逐账户 `diff=0`、退出码 0；
⑦ 幂等：连跑两次第二次删 0 行；⑧ `--rollback` 恢复行数并**响亮打印**"正在恢复 N 行非交易日净值行"。

### G · 常驻巡检判据 + 注释纠正
**实施**：新建 `tools/check_nontrading_equity_snapshots.py`（查 `quant.simulation_equity_snapshot` ⋈
`quant.trading_calendar`，非交易日行 → 退出码 2 并列出账户/日期；干净 → 0；自身出错 → 3）；
新建 `tests/test_check_nontrading_equity_snapshots.py`（造脏行证明检查器是活的）；
改 `application/services/trading_day_guard.py` **仅 docstring**（删失真声明）。
**验收**：`./venv/bin/python -m pytest tests/test_check_nontrading_equity_snapshots.py -q` 全过，且
① 干净库退出码 0；② 插入一行周末净值行后退出码 2 且输出含该账户与日期；③ 日历缺行的日期**不误报**为违规（单列 warn）；
④ 检查器自身异常退出码 3；⑤ `grep -c is_synthetic application/services/trading_day_guard.py` == 0。

### E · 跨仓消费侧（agent-dh）
**实施**：改 `agent-dh/packages/tools/risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts`
（`probeNavCoverage` 改读 v2 `nav_coverage`；缺字段 → `verified:false` 文案）；
改同目录 `prompt.ts` 文案（"工作日" → "交易日"）；
改 `agent-dh/apps/web/tests/attribution-alignment.test.ts`。
**验收**：`cd ../agent-dh && npx vitest run apps/web/tests/attribution-alignment.test.ts` 全过，且
① v2 给 `nav_coverage` 时原样透出（含 `basis`/`trading_day_source`）；
② v2 缺字段时输出"未做交易日校验"且**不触发补跑建议**；③ 覆盖 `09-30→10-08` 场景缺口为 0；
④ 缺真交易日仍报缺口（证明判据是活的）；⑤ 该文件内不再出现 `getUTCDay` 形式的交易日判定。

## 5. 批次与依赖顺序

```
批 1（契约与闸门，互不依赖）       批 2（接线与清理，均依赖批 1）           批 3
  A nav_series 口径 ─┬────────────► D 读取端接线 ──────────────► E agent-dh 消费
  B 仓储闸门 ────────┼────────────► C 写入入口接线
                     ├────────────► F 存量清理迁移
                     └────────────► G 常驻巡检判据
```

- **无前向引用**：C→B、D→A、B、F→B、G→B、E→D，全部指向数组里更早的 key。
- **批 1 的两张卡可并行**：A 只碰 services 层新增模块与 shim，B 只碰仓储层行为。
- **E 排在最后**：它是**消费方**，必须等 D 把 `nav_coverage` 真正返回后才能接。

## 6. 验收命令（与 `design/test-cases.md` §7 同口径）

```bash
./venv/bin/python -m pytest tests/test_nav_series.py tests/test_equity_snapshot_trading_day_gate.py \
    tests/test_equity_snapshot_daily_return.py tests/test_daily_jobs_trading_day_gate.py \
    tests/test_risk_metrics_nav_window.py tests/test_migration_purge_nontrading_snapshots.py \
    tests/test_check_nontrading_equity_snapshots.py -q
./venv/bin/python tools/check_nontrading_equity_snapshots.py                      # 期望退出码 0
./venv/bin/python tools/verify_equity_snapshot_consistency.py --accounts agent_virtual,user_main_simulation,v13_simulation,v14_simulation,v15_simulation
cd ../agent-dh && npx vitest run apps/web/tests/attribution-alignment.test.ts
```

## 7. 边界（不做什么 · 防范围蔓延）

1. **不改调度排班 / misfire 宽限**（归 `REQ-261006093620-a315`）。
2. **不修基准数据链**（D-5）：`nav_coverage` 只报净值序列自身缺口。
3. **不加"是否交易日"列**、不改 `simulation_equity_snapshot` 的键与列。
4. **不动 `quant.trading_calendar` 的日历数据**。
5. **不重构 sync/async 双轨仓储**。
6. **不做前端产物**（side 全为 backend）。
7. **`force=True` 不得出现在生产路径**（只在迁移脚本与测试中显式书写）。

## 8. 批准门与下一步

批准本计划 → 自动落库 7 张任务卡并进入实施（不再中途打断）。
未获批准前 `reqboard_decompose` 被代码级拒绝。
