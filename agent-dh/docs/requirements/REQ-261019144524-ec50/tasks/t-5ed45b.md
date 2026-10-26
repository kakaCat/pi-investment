# t-5ed45b 落地观察计分 SOP（signal_track 全级别纳入+回填核查）·复核

> 子卡（父卡 t-557f90 · 阶段 review）——由自动实施链展开；本卡文档在验收前按 queue.json 台账回填（2026-10-19，w-503df447）。

## 在做什么
落地观察计分 SOP（signal_track 全级别纳入+回填核查）·复核

## 状态
done（lastRun.ok=True）

## 完工记录（台账回填，原文）

- 对父卡实施方案①②③逐条复核探针阶段（t-c7a81f）产出与代码/数据事实：①确认 record/update 调用点——无偏离。探针报三处调用点，复核全部坐实：PortfolioTradeTool.trackSignal（BUY 成交自动记录，PortfolioTradeTool.ts:558，C 级因不交易走不到此路径）、opportunity-funnel SKILL:57-58（明文"每只存活标的我 signal_track(record)，C 级也要落"）、deep-analysis SKILL:41（定级后落库不分级）。②补 C 级落 track 例程/SOP——有偏离（交付缺口）。机制层面 C 级落库+回填已闭环（report 实调：82 信号中 C 级 53 条占 64.6%，C 级 5 日胜率 26.5%/10 日 33.3% 已有回填值，recentSignals 多条 C 级"只观察不交易"仍被 record），探针据此证伪父卡"当前只观察不落库"的前提属实；但父卡验收要求的交付物 w3-observe-scoring-sop.md 不存在（ls 确认目录仅有 w1/w2），且本子链只有 probe+review 两段、无任何阶段承接"成文 SOP"产出——缺口真实存在且无人兜底。③核查 signal_perf_backfill_daily 覆盖度——代码层无偏离。signal_tracking_service.py:113 update_performance 经 get_signals_after_date 取数、不按 grade 过滤（A/B/C 同级回填坐实）；signal_jobs.py SignalPerfBackfillJob（name=signal_perf_backfill_daily、lookback_days=30）已注册；探针引用的运行时状态（启用/27 次/last=2026-10-16）属 scheduler_manage 证据，复核未重跑（父卡终态验收命令，留测试段），但 report 中 5/10 日胜率非空可间接佐证回填在跑。综上：①③无偏离，②有偏离（SOP 文档交付缺口+父卡前提需修正），判 fail 提请父卡处置。
