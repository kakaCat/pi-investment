# W3 观察计分 SOP：signal_track 全级别纳入 + 回填核查

- **需求**：REQ-261019144524-ec50 进化闭环有效性改造（SP-3 / 工作包 W3）
- **任务**：t-557f90（探针子卡 t-c7a81f · 复核子卡 t-5ed45b）
- **落盘**：2026-10-19 · w-503df447（investor）
- **衔接**：本 SOP 维护的信号库是北极星 **KPI-1 信号胜率** 的唯一数据源（见 [w2-northstar-kpi.md](w2-northstar-kpi.md) §1）——漏记直接污染 KPI-1。

## 0. 前提修正（探针证伪，复核确认）

**父卡原前提「C 级信号当前只观察不落库、导致样本流失」被实测证伪。** 机制层面 C 级落库与回填**已闭环**：

- C 级已大量落库：signal_track report（2026-10-19 实调）82 条信号中 **C 级 53 条（64.6%）**，且 C 级 5 日胜率 26.5%、10 日胜率 33.3% 已有回填值；recentSignals 中多条 C 级 reason 明确写「只观察不交易」仍被 record。
- 回填覆盖全级别：`signal_tracking_service.update_performance`（signal_tracking_service.py:113）经 `get_signals_after_date` 取数、**不按 grade 过滤**，A/B/C 同级回填。
- record 现有调用点三处（复核逐条坐实）：
  1. `PortfolioTradeTool.trackSignal`（PortfolioTradeTool.ts:558）——BUY 成交自动记录（C 级不交易，走不到此路径）；
  2. 技能 SOP：opportunity-funnel SKILL:57-58（明文"每只存活标的我 signal_track(record)，C 级也要落"）、deep-analysis SKILL:41（定级后落库不分级）；
  3. agent 例程手动调用（source=manual 28 条为证）。

**真实缺口**：落库靠 agent 自觉、无成文 SOP、无漏记核查例程——哪天某个任务忘了 record，没有任何机制会发现。本 SOP 固化的就是这个缺口。

## 1. 记录纪律（何时 / 怎么 / 谁来）

### 1.1 何时必须 record

**任何产出 A/B/C 分级结论的场景，当场 record，不分级别、不论是否交易**：

| 场景 | 触发点 |
|---|---|
| opportunity-funnel 技能 | 每只存活标的定级后（SKILL 已明文，本 SOP 与之互引） |
| deep-analysis 技能 | 定级后立即落库（SKILL:41） |
| 盘中异动扫描（intraday-surge-scan 等 Agent 任务） | 每个给出分级结论的标的 |
| 盯盘规则触发后的人工/自动研判 | 给出分级结论时（含"不追""等回踩"等否定性结论——它们也是信号） |
| 手动分析得出分级结论 | 当场 record，source=manual |

**否定性结论（C 级只观察、B 级等回踩、涨停不追）同样是信号**——它们 5/10/20 日后的表现正是"我的否定判得对不对"的计分材料，不记录就等于放弃复盘样本。

### 1.2 怎么 record（参数规范）

`signal_track(action=record, symbol, grade, price, source, reason)`：

- **grade**：A/B/C 按 R-009 定义，禁止为了"好看"降级不记；
- **price**：决策时点价格（realtime 口径，R-013）；
- **reason** 必含三要素：①分级依据（哪几维共振/矛盾，各维数据来源工具+时点）；②约束（冻结期/已涨停不追等）；③后续动作（只观察/挂触发/等回踩价位）；
- **source**：strategy_execute / opportunity_scan / mainline_stocks / watch_rule / manual 五选一，如实填写。

### 1.3 谁来 record

**产出分级结论的窗口/任务本人**，当场 record——不留给下游、不假设"别人会记"。

### 1.4 禁止项

- 同一标的、同一逻辑、同一交易日**不重复 record**（当日已有同标的信号先查 recentSignals）；
- C 级信号**禁止委托**（R-009），record 是唯一动作；
- 验收/测试性质的 record 必须在 reason 开头标注【测试】，避免污染胜率统计解读。

## 2. 回填核查例程（本 SOP 新增，补"无人发现漏记"缺口）

### 2.1 每日盘后（挂 post-market-routine 例程执行）

1. `signal_track(action=report, start_date=今日, end_date=今日)`：核对当日已记录信号条数与当日各任务日志中给出过分级结论的标的数是否一致；发现漏记 → 当场补录（reason 注明"盘后补录"）。
2. 当日 C 级占比异常（=0 或 =100%）时自查是否分级尺度漂移。

### 2.2 每周（挂 weekly-report-m6 的 KPI 采集段，与 KPI-1 取数同次执行）

1. **回填停滞检查**：`scheduler_manage(action=list)` 确认 `signal_perf_backfill_daily`（任务 ID 1deba5ac-c4a1-459e-918c-b087d9ed7bbd，工作日 15:45）近 7 日内有 ✅ 成功运行；last 运行距今 >2 个工作日 → 飞书告警（alerts, normal）。
2. **回填覆盖率抽查**：report 取近 30 日窗口，`price5D` 为 null 且 signalDate 距今 >7 个交易日的信号应趋近 0；非零则核查 backfill 任务日志。
3. 口径备忘：回填不按 grade 过滤（§0），A/B/C 同级；hitRate20D 回填滞后约一个月，近 4 周窗口 null 属正常（w2 §1 注意项）。

## 3. 验收锚点（本卡三项，全部 2026-10-19 实测）

- [x] **SOP 落盘**：本文件（docs/requirements/REQ-261019144524-ec50/w3-observe-scoring-sop.md）。
- [x] **record→report 链路可见**：signal_track(record) 写入测试信号 **ID 166**（600011，C 级，reason 标注【SOP验收测试信号】），随后 signal_track(report, 2026-10-19~2026-10-19) 返回 4 条信号含 ID 166（2026-10-19 22:19 实调）。
- [x] **signal_perf_backfill_daily 近 7 日运行 ✅**：scheduler_manage(action=list)（2026-10-19 实调）显示该任务 ✅ 启用、已运行 27 次、上次 2026-10-16T15:45、上次结果 ✅。

## 4. 边界

- 本 SOP 只固化"记录与核查"，**不改 R-009 分级阈值、不改任何交易规则**（本需求不动交易规则，design §1）；
- 信号库的清洗（如测试信号 ID 166 的后续处置）属数据卫生议题，如需删除走 R-020 契约登记与 decision_audit 留痕，不在本卡动作内。
