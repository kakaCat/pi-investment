# v2 Job 假成功壳修复：chan_scan (261) / chan_knowledge_distill (262)

- 日期：2026-09-05
- 角色：PI 投资顾问·投资脑（investor，窗口 w-d84dc7b1）
- 范围：quantsys-v2 `application/jobs/analysis_jobs.py`（Fix⑥）

## 一、问题

261 `chan-scan-daily`（chan_scan，周一至五 22:30）与 262 `chan-knowledge-distill-weekly`
（chan_knowledge_distill，周日 12:00）两个 v2 JobRegistry 定时任务，execute 均为**占位空壳**：

- `ChanScanJob.execute` → `JobResult.ok(... message="缠论扫描完成（待实现）", details={"scanned": 0})`
- `ChanKnowledgeDistillJob.execute` → `JobResult.ok(... message="缠论知识蒸馏完成（待实现）", details={"distilled": 0})`

自 09-02 JobRegistry 接管 261 起，**假成功记录每日落库**（runs 3340/3370/3381/3392/3409
全 `details.scanned: 0`，message「待实现」）。262 则自 08-25 历史 IndentationError 时代后
从未真实蒸馏（上次真实产出 08-16：`signals_total=33 → strategies_distilled=6`）。

假成功壳 = 系统性静默退化：任务永不报错、永远 success，调度器/巡检无从察觉真实能力已停摆。

## 二、历史能力证明（真实运行证据）

| 任务 | run | 时间 | 真实结果 |
|---|---|---|---|
| 261 chan_scan | 2843 | 2026-08-17 19:04 | `scanned=53, skipped=13, errors=0` |
| 262 distill | 2752 | 2026-08-16 20:00 | `signals_total=33, excluded=1, strategies_distilled=6` |

即：真实服务链本就可用，壳的「待实现」是**回归而非初始缺陷**。

## 三、根因链条

1. **08-21 P2-1 DI 标准化**（d87297e6）：`ChanScanService` / `ChanKnowledgeDistiller` /
   `ChanService` 改为构造注入 repo，参数 Optional、**无默认实例化兜底**：
   - `ChanScanService()` 无参 → `_pool_repo=None` → `scan()` 调 `_pool_repo.get_all()` 即崩；
   - `ChanService()` 无参 → `kline_repo=None` → `_fetch_kline_data` 内部 try/except 吞错
     返回空 DataFrame → analyze 恒「无K线」→ 扫描全部 skipped（静默空结果）；
   - legacy `handle_chan_scan` / `handle_chan_knowledge_distill`（scheduler_tasks.py）仍无参
     构造 → 08-25 起这两条 legacy 路径已不可用（正是 08-25 IndentationError 前后开始失败）。
2. **09-02 JobRegistry 迁移**：注册 ANALYSIS_JOBS 内的 ChanScanJob/ChanKnowledgeDistillJob，
   而这两类 execute 是占位空壳 → legacy 不可用 + 壳假成功，双保险全失。

## 四、修复方案（Fix⑥，同 StrategyValidateDailyJob Fix④ 模式）

`analysis_jobs.py` 两 execute 改为 lazy import + **显式注入 ORM repo** 委托真实服务，
不依赖 EnhancedServiceFactory（其 chan 相关服务注册在 job 运行时无人保证已 register，
实测 `resolve(IAgentKnowledgeRepository)` 报 "Service not registered"，仅降级不阻塞）：

- `ChanScanJob.execute`：
  ```python
  ChanScanService(
      chan_service=ChanService(kline_repo=KlineORMRepository()),
      pool_repo=StockPoolRepository(),
      signal_repo=SignalORMRepository(),
  ).scan()
  ```
- `ChanKnowledgeDistillJob.execute`：params 透传 window_days/lookback_days（默认 20/90），
  ```python
  ChanKnowledgeDistiller(window_days=…, lookback_days=…,
      signal_repo=SignalORMRepository(),
      kline_repo=KlineORMRepository(),
      knowledge_repo=AgentKnowledgeORMRepository(),
  ).distill()
  ```
  蒸馏结果幂等 upsert 至 agent_knowledge（chan_theory/signal_effectiveness）。

**details 落库形状修正**：`JobResult.ok` 签名是 `ok(action, message="", **details)`——
传 `details={...}` 会被包成 `details: {details: {...}}` 双层（历史 3409 壳、Fix④ 均双层）。
本次改为 `**summary` 展开，落库扁平，与 legacy 真实成功时期（run 2752）一致。

## 五、验证

1. 单测新增 `tests/jobs/test_chan_jobs.py` 6 例（mock 服务验证委托+参数透传+JobResult
   契约+失败诚实路径）；全套 chan 相关 68 passed，无回归。
2. 真实端到端（py313 直跑 execute，走真实 DB）：
   - 262：`success=True`，`strategies_distilled=6, signals_total=30, excluded=0`
     （30 条 chan_ 信号为 06-01 后存量 33 条中 lookback 窗口内命中数，与 08-16 量级吻合）；
   - 261：`success=True`，`scanned=53, written=0, skipped=0, err=0`
     （scanned=53 与 08-17 真实 run 完全一致；written=0 因当日无新买卖点匹配，create_signal
     幂等键 (symbol, signal_date, strategy_id) 冲突返 0 计 duplicates，不会重复污染）。

## 六、遗留（非本次范围）

- 237/250/253 仍为 count-only 壳、258 缺调用括号、north_flow 描述、daily klines 同步滞后
  等已知待办；chan API 侧 chan_async.py 仍走旧 ServiceFactory 无 kline_repo（analyze 空K线
  降级），未在本次接线范围内。
