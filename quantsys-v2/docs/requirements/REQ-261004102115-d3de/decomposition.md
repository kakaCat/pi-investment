# REQ-261004102115-d3de 拆分计划：应有交易日接节假日日历

**需求**: REQ-261004102115-d3de《健康探针节假日盲区：新鲜度判定未接交易日历（国庆误报）》
**档位**: 轻档 · **设计**: design/ 五份已确认落章
**目标**: 把"最近一个已收盘交易日"做成唯一实现（节假日感知），探针与 freshness_guard 复用，
消除休市期的 K 线新鲜度误报，并用日期用例锁死。

## 一、改动盘点（对照设计逐份）

| # | 动作 | 文件 | 依据 | 归属卡 |
|---|---|---|---|---|
| 1 | **新增** | `application/services/trading_day_resolver.py` | architecture.md 落点段 | t1 |
| 2 | **新增** | `tests/test_trading_day_resolver.py` | test-cases.md 用例 1-10 | t2 |
| 3 | **新增** | `tests/test_health_probe.py` | test-cases.md 用例 11-13 | t3 |
| 4 | **修改** | `tools/health_probe.py`（expected_trading_day / probe_freshness / build_alert） | interfaces.md 探针输出契约 | t3 |
| 5 | **修改** | `adapters/inbound/fastapi_app/daily_jobs/pipeline.py:237`（`_last_trading_day` 内部实现；76/177 调用点不动） | interfaces.md 调用点契约 | t4 |
| 6 | **修改** | `tools/refresh_trading_calendar.py`（源改 provider，并集保留 klines） | data-model.md 刷新脚本段 | t5 |
| 7 | **数据** | `quant.trading_calendar` 一次性回填（只写 TRUE/FALSE） | data-model.md 回填段 | t5 |
| 8 | **不改** | `deployment/launchd/com.pi-investment.health-probe.plist`、`quant.data_contracts`、K 线数据、ORM/迁移 | requirement.md「不做什么」 | t6 核验 |
| 9 | **不改** | `tools/check_data_contracts.py:compute_expected_trading_day`（已正确，登记为后续收敛项） | architecture.md 第三个口径段 | — |

无删除项。**无 DDL 变更、无 ORM 变更、无新第三方依赖。**

## 二、任务表

| key | 标题 | phase | side | 依赖 | 承接条款 |
|---|---|---|---|---|---|
| t1 | 实现交易日解析器（最近一个已收盘交易日） | implement | backend | — | FR-1 |
| t2 | 写日期表驱动回归用例（含降级与周末语义） | test | backend | t1 | FR-1, FR-4 |
| t3 | 探针接入新口径并标注判定来源 | implement | backend | t1 | FR-2, FR-4 |
| t4 | freshness_guard 复用同一实现 | implement | backend | t1 | FR-3 |
| t5 | 刷新脚本改接 provider 源并一次性回填日历表 | implement | backend | t1 | FR-1 |
| t6 | 核验迁移与兼容（管道读表切换、引用方、无新依赖） | analysis | backend | t3, t4, t5 | FR-1, FR-3 |

### 卡内验收（可证伪）

- **t1**：`./venv/bin/python -c "…last_closed_trading_day(datetime(2026,10,4,10,18))…"`
  → 日期必须为 `2026-09-30`，`source ∈ {calendar_table, provider}`、`degraded=False`。
- **t2**：`./venv/bin/python -m pytest tests/test_trading_day_resolver.py -q` 退出码 0、用例 ≥10；
  删掉任一日期断言必须变红。
- **t3**：`./venv/bin/python tools/health_probe.py --dry-run` → `healthy=true`、`expected=2026-09-30`、退出码 0；
  `--max-lag-days -1` → 退出码 2；`pytest tests/test_health_probe.py -q` 全过且 notify-guard `egress=0`。
- **t4**：`_last_trading_day(datetime(2026,10,4,10,18))` → `'2026-09-30'`；
  `pytest tests/ -q -k freshness` 无新增失败。
- **t5**：`refresh_trading_calendar.py --dry-run` 行数 >0；回填后
  `SELECT count(*), max(trade_date) FROM quant.trading_calendar` → `max >= 2026-12-31`。
- **t6**：`load_trading_calendar_from_db('SSE')` 返回非空且不再打
  `trading_calendar_empty_fallback_to_klines`；`git diff --stat` 不含 launchd / pyproject / 契约迁移。

## 三、依赖与顺序

```
t1 ─┬─ t2（回归锁先立）
    ├─ t3 ─┐
    ├─ t4 ─┼─ t6（兼容核验，最后做）
    └─ t5 ─┘
```

t2 与 t1 之间是"契约先行、用例紧随"；t3/t4/t5 三条接线互不依赖，可并行；
t6 依赖三条接线全部落地，且必须**实际读一次表**才允许收尾。

## 四、风险与已登记代价

| 风险 | 处置 |
|---|---|
| 表未覆盖 anchor 时探针每 5 分钟走一次 provider | 已登记（data-model.md）；一次性回填后覆盖至年底；加排班属调度层，**本次不做** |
| 回填后 `load_trading_calendar_from_db` 从"回退 K 线"切为"读表" | 这是该函数注释要求的方向；回退路径不改，清表即回滚；t6 实测核验 |
| provider 不可用 → 回落到周一至周五口径（节假日仍会误报） | 属**响亮降级**：`expected_degraded=true` 进 JSON 与告警正文 |
| 现有断言硬编码"周一至周五"语义的用例 | t4 的核验命令会暴露；按 test-cases.md「既有用例的回归面」更新并在汇报里列出 |
