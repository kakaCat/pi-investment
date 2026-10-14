# REQ-261006163444-8e4f · 迁移 / 兼容 / 回滚清单

（对应拆分计划 t8；内容按设计 `data-model.md` §1/§5、`architecture.md` §5 落地）

## 1. 零 schema 变更（声明与依据）

**本需求不改表、不加列、不做迁移。** 依据：

- 分域快照（可交易域 / 观察中 / 存量）由 `quant.daily_klines.trade_date` **现算**：
  `SELECT DISTINCT trade_date ... ORDER BY DESC LIMIT 5` + `GROUP BY symbol` 的 `MAX(trade_date)`；
  "上期在域"就是倒数第二个交易日，不需要持久化域快照。
- 告警统计改读本次 run 内存里的 `per_symbol`，不再依赖审计表的当日行数，
  因此也**不需要**给 `public.kline_data_quality` 加 `run_id` 列。
- 唯一的数据行变更是**配置行**（§3），非 schema。

> 升级信号（本设计已排除）：若日后要把"域"落成持久化状态（按日归档域快照以便回溯），
> 才需要一次迁移。

## 2. 旧调用方核对清单

| 调用方 | 结论 |
|---|---|
| `infrastructure/jobs/data_quality_check_job.py`（`daily_data_quality_check`） | **已改**：建快照 → 域内聚合 → 新告警签名；`per_symbol` 只在本 run 内消费 |
| `adapters/inbound/fastapi_app/routes/data_quality_async.py:162` | **无需改**：只读既有键（`summary` / `stocks_with_issues`），新增 `per_symbol` 对其透明 |
| `tests/test_data_validator_anomaly_detection.py:212` | **无需改**：同上，只读既有键 |
| `tests/test_data_quality_job_guardrails.py:70`（`FakeService.check_data_quality` 替身） | **已改**：补 `per_symbol` 与 `kline_repo`（分域快照需要）；4 处 `_send_quality_alerts` 调用改新签名 |
| `KlineQualityRepository.count_by_grade_on` 的调用方 | 作业层已**退出**该调用（改读 `per_symbol`）；方法本身保留并修正为 distinct 语义，供人复核 |
| `grep -rn "check_data_quality(" --include='*.py'`（9 处） | 其中 4 处是定义/同名异类（`domain/quantlib/data_validator.py` 的私有 `_check_data_quality`、`route`、两个测试），其余即上表各项 |

## 3. 配置行变更与回滚

| 项 | 值 |
|---|---|
| 表 / 行 | `quant.scheduler_tasks` id = 232（每日数据质量检查） |
| 变更 | `params.quality_threshold`: **95.0 → 88.0**（jsonb 合并，`UPDATE ... params \|\| '{"quality_threshold": 88.0}'`） |
| 已执行 | ✅ 2026-10-06 本机执行，变更后 `params` 实测含 `"quality_threshold": 88.0` |
| 回滚 | 把该键改回 `95.0`（同一条 jsonb 合并语句） |

**为什么改**：旧值 95.0 与旧口径的评分上限（`0.6×覆盖率+40` = 95.02）只差 0.02 分，
等价于"永久红灯"；新口径域内现值 90.84，88.0 留 ≈2.8 分余量。
新增的三个键（`d_grade_threshold=20` / `coverage_info_threshold=97.0` / `backfill_min_sample=10`）
都有代码缺省，**不写库也能跑**；本环境未写库，仅代码缺省生效。

## 4. 历史数据的阅读口径

- `public.kline_data_quality.original_count` 在本需求之前**恒为 0**（代码取的是不存在的键
  `expected_days`，真实键是 `total_trading_days`）。历史行**不追改**，阅读时按"该列当时不可用"理解；
  自本需求上线后的新写入行才是有效值（窗口交易日数）。
- 2026-10-06 当天的评级行是"同日两次运行各写一行"（00:00 自动 + 13:48 手动），
  按标的去重才是真值（D 级：806 行 / **404 只**）。

## 5. 部分回滚路径

| 回滚范围 | 动作 | 后果 |
|---|---|---|
| 只回滚告警口径 | 还原 `data_quality_check_job.py` + `kline_domain.py` + 配置改回 95.0 | 回到"死标的入域 + 同日多跑翻倍"的旧红（D级 806 / 评分 86.28 / 失败率 71.4%） |
| 只回滚回填限域 | 还原 `_select_backfill_targets` 的调用处 | 回到"额度被退市股吃掉、374 条无效 `All data providers failed`" |
| 全量回滚 | 还原提交 + 配置改回 95.0 | 无数据回滚动作（零 schema 变更）；新写入的非 0 `original_count` 保留，旧代码不会再写但也不会读错 |

## 6. 本次实施状态（交接用 · 2026-10-06）

**已完成并实测（代码 + 用例）**

| 卡 | 内容 | 证据 |
|---|---|---|
| t1 | `application/services/kline_domain.py` 分域纯函数 | `tests/test_kline_domain.py`（14 条含集成回归锁）全绿；纯函数无 DB 依赖 |
| t2 | 仓储两个只读方法 + `count_by_grade_on` 改 distinct | 实测 `list_recent_trade_dates(2)` → `['2026-09-30','2026-09-29']`；`len(list_symbol_last_trade_date())=5686`；`count_by_grade_on('D')` **806 → 404** |
| t3 | `check_data_quality` 返回全量 `per_symbol` + `original_count` 取键修正 | 实测 `per_symbol['600519']` 8 键齐；审计 `original_count` **0 → 60**；`overall/grade` 与审计同源一致 |
| t4 | 作业层接线（域快照 / 域内聚合 / 新判据 / 回填限域 / 结果新键） | 真库端到端小样本实跑：`domain={tradable 5280, observing 3, stock 403}`、`alert_scope=tradable`、正文三段齐、`per_symbol` 未入 result |
| t5 | 分域用例 | `tests/test_kline_domain.py` |
| t6 | 告警口径用例 + 反例锁 | `tests/test_data_quality_alert_scope.py`（12 条，含 L1 同日两行不翻倍、L2 旧口径必误报）；既有 `test_data_quality_job_guardrails.py` 17 条全过 |
| t7 | 配置变更 | 已执行（§3）；**全市场实跑复验未做**（见遗留 2） |
| t8 | 本文件 | —— |

**总计**：`pytest tests/test_kline_domain.py tests/test_data_quality_alert_scope.py tests/test_data_quality_job_guardrails.py tests/test_data_validator_anomaly_detection.py -q` → **59 passed**，`notify-guard intercepted=0 egress=0`。

**实施中发现并修正的两处（设计稿与实现不一致，已在设计文档内就地订正并留痕）**

1. `gap` 公式笔误：设计写 `rank(D_last) - rank(mx)`，正确为 **`gap = rank(mx) - 1`**
   （`interfaces.md` §1 / `data-model.md` §2 / `decomposition.md` t1 三处已订正）。
2. **交易日要取够 5 个**：`build_domain_snapshot` 起初按设计只取最后 2 个交易日，
   导致"隔 2~4 个交易日"的标的名次查不到 ⇒ 被静默丢进存量（实测观察中假报 2 只 / 存量 404 只）。
   改为取 `STOCK_MIN_GAP` 个后为 **3 / 403**，并补了回归锁
   （`test_contract_build_snapshot_asks_enough_trade_dates`）。
   ——这条正是"只跑单测不跑集成就发现不了"的典型，故一并记录。

**遗留（下一窗口接手做）**

1. **卡片台账收尾**：t2 / t3 / t4 / t5 / t6 / t7 / t8 的实现均已完成，但各卡的「研发 / 联调 / 复核 / 测试」
   子卡台账尚未逐张关闭（本窗口预算触顶）。按卡内容与上表证据逐张汇报并 `reqboard_task_move(to=done)` 即可，
   不需重做代码。
2. **全市场实跑复验**（t7 的第二半）：手动触发一次 task 232（全市场 5686 只，约 5 分钟），
   采集告警正文与最新 run 的 `result.domain` / `domain_dropped` / `alert_scope` / `alert_thresholds`，
   并核对 `All data providers failed` 新增条数为 0（今日基线 374）。
3. 子卡验收模板给的是 `npx vitest` / `pnpm test`（本仓为 Python），按 `pytest` 口径自证——
   属平台模板问题，已如实登记在本文件与各卡汇报里。

## 7. 全市场实跑复验（2026-10-06 16:51–16:53，t7 后半）

| 验收项 | 结果 | 证据 |
|---|---|---|
| ① 正文三段齐、不含旧两条告警 | ✅ | 正文见下 |
| ② `alert_scope == tradable`、域内计数 | ✅ | `domain = {tradable 5280, observing 3, stock 403, stats_symbols 5280, partial false, degraded false}` |
| ③ `All data providers failed` 新增 = 0 | ❌ **未达标（150 条）** | 见下「新发现」 |
| ④ 新写入行 `original_count > 0` | ✅ | 抽查 `original_count = 60`（窗口交易日数） |

实跑正文（节选）：

```
📊 数据质量告警（3 项）
口径: 可交易域（最后交易日 2026-09-30）｜统计 5280/5280 只
检查域: 可交易 5280 ｜ 观察中 3 ｜ 存量 403
本期掉出可交易域: 2 只   002813、603183
域内指标: 评分 90.87（阈值 88.0）｜覆盖率 98.58%（信息项）｜D级 1 只（阈值 20）
```

**关键**：旧的两条（D级 806 过多 / 评分 86.28 偏低）**确实不再出现**，评分与覆盖率回到域内真值。

### 新发现（本需求未能修掉的第 4 个缺陷，建议进后续线）

回填 **50 只目标全部失败（0/50，失败率 100%）**，`All data providers failed` 150 条（3 轮重试 × 50）。
原计划假设「把退市标的剔出候选集 ⇒ 失败率下降」**不成立**。真因：

- Top-50 目标是按"缺失天数降序"选出的，实际选中 **9200xx / 688xxx 等次新与北交所标的**
  （920000…920011、688825…），它们的"缺失段"是**窗口起点 2026-07-08 起的那一段**；
- 这些标的的可获取历史晚于窗口起点（如 920018 首条 K 线 2025-08-20 之后、920060 为 2024-11-19），
  数据源对"上市前 / 无历史"的区间**本来就取不到** ⇒ 每次必失败、每轮重试必失败；
- 后果：新口径下**每天都会发 2 条 error 级告警**（回填失败率 100% + 回填全灭），"去伪"只完成了一半。

**建议后续线（需人裁决是否另开需求）**：
1. 回填目标不应只看"缺失天数"，应排除**窗口起点早于标的首条 K 线**的区段（缺口本就不该存在）；
2. 或按"标的自身可获取区间"裁剪回填请求范围，而不是用全局窗口；
3. `backfill_failed` 的语义应区分「数据源不可用」与「该区间本无数据」——现在两者同名，导致失败率失真。
