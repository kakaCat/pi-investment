# REQ-261004102115-d3de: 健康探针节假日盲区：新鲜度判定未接交易日历（国庆误报）

**需求ID**: REQ-261004102115-d3de
**类型**: feature（缺陷修复性质）
**作用域**: `quantsys-v2/`（`tools/health_probe.py`、`adapters/inbound/fastapi_app/daily_jobs/pipeline.py`、`tools/refresh_trading_calendar.py`、`tests/`）
**档位**: 轻档（L3 依据见文末；出现"第二个未定决策 / 动架构 / 新增子系统 / 改数据模型"即单向升级重档）

## TL;DR

**这条告警是误报，数据没问题。** 探针把 **2026-10-02（国庆休市日）** 当成"应有交易日"，
于是算出 K 线滞后 2 天；而 A 股自 **2026-09-30 收盘后即进入国庆休市**，
**下一交易日是 2026-10-08（周四）**——09-30 就是当下最新的真实交易日。

根因一句话：**"哪天该有数据"这套口径只排周末、不排节假日**。

```
daily_jobs/pipeline.py:237  _last_trading_day()   ← 只 while d.weekday() >= 5 回退，节假日一律当交易日
tools/health_probe.py:71    from ... import _last_trading_day   ← 探针直接复用它
                            └─▶ 2026-10-04（周日）→ 10-03(六) → 10-02(五) = expected
                              lag = (10-02 − 09-30) = 2 > max_lag_days=1 → 报警
```

**官方口径**（上证公告〔2026〕22 号）：9 月 25 日（五）至 9 月 27 日（日）休市、9 月 28 日开市；
**10 月 1 日（四）至 10 月 7 日（三）休市，10 月 8 日（四）起照常开市**。

## 边界

### 做什么

1. **把"应有交易日"改成节假日感知的单一实现**：语义 = **最近一个已收盘的交易日**
   （今天为交易日且已过 15:30 则为今天，否则回溯到最近一个交易日），真源为 A 股交易日历。
2. **探针改用该口径并显式标注来源**：报告与告警正文必须能看出"这一步是日历判的，还是降级成工作日判的"。
3. **进程内 `freshness_guard` 复用同一实现**：消除 2026-10-02 那条同源误报（同一根因的第二个出口）。
4. **回归锁**：新增可跑的日期用例，把国庆/中秋这类休市日钉死，防止下次换个节日再犯。

### 不做什么

- **不修 `evening_pipeline` 在休市日空跑 `kline_sync` 的行为**（10-02 那次成功 0 只、未覆盖 5271 只）——
  属"休市日是否该起同步"的另一个决定，本次只登记、另案处理。
- **不改 `quant.daily_klines` 的内容，也不改 `quant.data_contracts` 的口径**
  （契约本就留了 `holiday_slack_weekdays=3` 的节假日宽限，本次修的是探针没跟上契约）。
- **不新增第三方依赖，不让探针 import 被监控服务进程**：探针"不依赖被监控进程"是它的立身之本
  （本仓已静默死亡 3 次，探针就是为这个立的）。

### 边界理由

- 用户可感知的成本只有一项：**误报告警**（每 5 分钟一次，会一直响到 10-08 收盘）。
  修法局部（1 个 helper + 2 个调用点 + 1 个测试文件），不需要动数据、也不需要动调度。
- 为什么带上 `freshness_guard`：它是**同一根因的第二个出口**——10-02 它同样报
  `status=stale / expected=2026-10-01`。只修探针 = 留着一个一模一样的复发点，
  且两者已共用同一个 `_last_trading_day`，改一处是改，改两处也是改。

## 产品定义

### 一句话

让"这份数据过期了吗"这件事按**真实交易日历**回答，而不是按"周一至周五"猜——
休市期间不再对着一份完好的数据喊救命。

### 为什么现在做

1. **正在发生，且用户已经看到了**：2026-10-04 10:18 的探针告警即由本次误报触发。
2. **误报本身会毁掉监控**：探针是为"服务静默死亡"立的；每 5 分钟一次的错误告警，
   一周就能把"告警 = 噪音"训练进人的条件反射（探针设计注里明确写了这条顾虑：告警疲劳 = 另一种静默死亡）。
3. **真源已经可用，代价极低**：`DataProviderManager.get_trading_calendar()`（akshare）实测已能正确
   排除国庆节，返回 `09-30 → 10-08 → 10-09 → 10-12`。不需要新依赖、不需要新数据采购。
4. **同类口径在本仓散落三处**（探针 / `freshness_guard` / `data_contracts`），只有第三处考虑了节假日——
   不收敛，下次春节、下次中秋必再犯。

### 现状实测（2026-10-04 10:18–10:25 采集，均可复现）

| 维度 | 实测值 | 证据 |
|---|---|---|
| K 线最新交易日 | `2026-09-30` | `SELECT max(trade_date) FROM quant.daily_klines` |
| 09-30 覆盖度 | 5276 只（与 09-24/28/29 的 5276 只一致） | 同上，按 `trade_date` 分组计数 |
| 探针判定 | `ok=false / expected=2026-10-02 / lag_days=2` | `./venv/bin/python tools/health_probe.py --dry-run` |
| 应有交易日（官方） | 下一交易日 `2026-10-08` | 上证公告〔2026〕22 号 |
| 日历真源可用性 | 可用，已排除 10-01~10-07 | `get_trading_calendar('2026-09-28','2026-10-12')` → 09-28/29/30、10-08/09/12 |
| `quant.trading_calendar` | **0 行**（建表后无人写入） | `SELECT count(*) ...` |
| 同源误报（进程内） | `freshness_guard` @ 2026-10-02 → `status=stale, expected=2026-10-01` | `quant.inprocess_job_runs.result` |
| 休市日空跑（登记，不修） | `evening_pipeline` @ 10-02：`kline_sync success=0 / 未覆盖 5271 只` | 同上 |
| 判定口径不一致 | 契约给 `daily_klines` 留了 `holiday_slack_weekdays=3`，探针是 `--max-lag-days 1`（自然日、无节假日宽限） | `quant.data_contracts.freshness` vs `deployment/launchd/com.pi-investment.health-probe.plist` |

## 用户与角色

- **项目所有者（人类）**：不该在休市日收到"K 线滞后"的告警；判定标准是"国庆期间探针安静，
  10-08 收盘后该响才响"。
- **窗口 AI Agent（本需求实施者）**：按 FR 逐条改，改动集中在 1 个 helper + 2 个调用点 + 1 个测试文件。
- **后续维护者 / 新会话**：需要一条明确的规则——**"应有交易日"只允许有一个实现**，
  新增任何新鲜度判定都必须调用它，而不是各自写一遍 `weekday()`。

## 功能点

**FR-1: 节假日感知的「应有交易日」单一实现**
提供一个统一入口（语义：**最近一个已收盘的交易日**），替代 `daily_jobs/pipeline.py:_last_trading_day`
的"只排周末"实现；输入为参考时刻，输出为日期 + 判定来源；交易日历真源与缓存策略在设计阶段定
（候选：`quant.trading_calendar` 表 / `DataProviderManager.get_trading_calendar()`）。
日历不可得时**允许**降级为"工作日"口径，但必须把降级事实带出来，不得静默。

**FR-2: 探针接入新口径并显式标注来源**
`tools/health_probe.py` 的新鲜度判定改用 FR-1 的实现；输出新增来源字段
（`expected_source: calendar | weekday_fallback`），并在告警正文中可见。
对外契约只做**增量**（新增键），既有键（`expected` / `kline_latest` / `lag_days` / `max_lag_days`）语义不变。

**FR-3: `freshness_guard` 复用同一实现**
`adapters/inbound/fastapi_app/daily_jobs/pipeline.py` 中两处 `_last_trading_day` 调用点
改走 FR-1；coverage 门槛、失败残留告警等既有判定逻辑不得改动。
（`_last_trading_day` 的对外导入路径需保持可用，或同步改掉全部引用方——由设计阶段定。）

**FR-4: 回归锁（日期用例）**
新增测试：以固定日期表驱动断言 FR-1 的输出，至少覆盖
① 2026-10-04（周日，国庆中）→ 2026-09-30；② 2026-10-08 15:30 前 → 2026-09-30、15:30 后 → 2026-10-08；
③ 2026-09-25（中秋休市）→ 2026-09-24；④ 周末回退（既有语义不回归）；
⑤ 日历源不可用时降级为工作日且来源标注为 `weekday_fallback`。

## 验收标准（跑什么、看到什么算过）

1. **误报消除**：`./venv/bin/python tools/health_probe.py --dry-run`
   → 输出 `"healthy": true`、`expected=2026-09-30`、`expected_source=calendar`，退出码 `0`。
2. **回归锁**：`./venv/bin/python -m pytest tests/test_health_probe.py -q` → 全过。
3. **负向不失效**：`./venv/bin/python tools/health_probe.py --dry-run --max-lag-days -1`
   → 仍判异常并 exit `2`（证明判据没被改空）。
4. **降级要响**：断网或日历源不可用时，报告含 `expected_source=weekday_fallback`，
   且探针**不因日历故障**返回 exit `3`（探针自身出错才允许 3）。
5. **进程内同源出口**：`freshness_guard` 在休市日的 `expected` 亦为最近已收盘交易日
   （可用固定时刻的单测覆盖，或在休市日实跑观察 `quant.inprocess_job_runs.result`）。
6. **无副作用**：`git diff` 不含 `quant.daily_klines` 写入逻辑、不含 `data_contracts` 口径改动，
   不新增第三方依赖。

## 轻档依据（L3）与升级信号

- **L1 一句话目标 + 可证伪判定**：见上「产品定义」与「验收标准」第 1、2 条（命令 + 期望输出都写死）。
- **L2 范围边界 ≤3 条**：见「做什么 / 不做什么」，显式排除休市日同步行为与数据契约改动。
- **L3 轻路径依据**：改动面小（1 个 helper + 2 个调用点 + 1 个测试文件），
  生效路径已在现网实证（同一条探针、同一份 launchd 作业）；
  待定决策只有 1 个（**日历真源与缓存策略**），留给设计阶段。
- **单向升级信号（出现任一即停手升级重档）**：
  ① 决定新增数据表 / 改数据模型；② 改动 `quant.data_contracts` 口径；
  ③ 需要把修法扩展到调度层（休市日是否跑同步）；④ 出现第二个未定决策（如"滞后天数怎么算"要重定）。
- **L4 批准闸门**：本文件落盘 → `reqboard_submit(kind=requirement)` 登记 → `reqboard_ask_confirm` 请人确认；
  未获批准不进入 design。
- **L5 产物照旧**：`requirement.md` 已落盘（即本文件），轻档只体现为文档短，不省产物。

## 附：证据采集命令

```bash
# 1) 数据事实
psql -h 127.0.0.1 -U mac -d quant_investment -At \
  -c "SELECT max(trade_date) FROM quant.daily_klines;" \
  -c "SELECT trade_date, count(distinct symbol) FROM quant.daily_klines WHERE trade_date >= '2026-09-24' GROUP BY 1 ORDER BY 1;"

# 2) 探针复现（不发送告警）
./venv/bin/python tools/health_probe.py --dry-run

# 3) 日历真源可用性
./venv/bin/python -c "
from infrastructure.services.service_factory import ServiceFactory
m = ServiceFactory.get_data_provider_manager()
r = m.get_trading_calendar('2026-09-28','2026-10-12')
rows = getattr(r['data'],'data',r['data'])
print([x['trade_date'] for x in rows])"
```

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |

> 🔴 **未被接收（4 条）**：FR-1、FR-2、FR-3、FR-4

<!-- reqboard:marks:end -->
