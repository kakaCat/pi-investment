# t-c7a81f 落地观察计分 SOP（signal_track 全级别纳入+回填核查）·探针

> 子卡（父卡 t-557f90 · 阶段 probe）——由自动实施链展开；本卡文档在验收前按 queue.json 台账回填（2026-10-19，w-503df447）。

## 在做什么
落地观察计分 SOP（signal_track 全级别纳入+回填核查）·探针

## 状态
done（lastRun.ok=True）

## 完工记录（台账回填，原文）

- 探针问题（可证伪）：「C 级信号当前是否未落 signal_track 库、且未被 signal_perf_backfill_daily 回填？」——答案：**否，父卡前提被实测证伪**。①C 级已大量落库：signal_track report 实调（2026-10-19）82 条信号中 C 级 53 条（64.6%），且 C 级 5 日胜率 26.5%、10 日胜率 33.3% 已有回填值，recentSignals 中多条 C 级 reason 明确写「只观察不交易」仍被 record（source=manual，由 agent 手动/技能 SOP 驱动落库）。②回填覆盖全级别：signal_tracking_service.update_performance 用 get_signals_after_date 取信号、**不按 grade 过滤**，故 A/B/C 同级回填；signal_perf_backfill_daily（任务 1deba5ac，cron 15:45 工作日，内部任务）✅启用、已运行 27 次、last=2026-10-16T15:45 ✅（在近 7 日内）。③record 现有调用点三处：PortfolioTradeTool.trackSignal（BUY 成交自动记录，C 级因不交易走不到此路径）、技能 SOP（opportunity-funnel/deep-analysis 明文要求 C 级落 track）、agent 例程手动调用（manual source 28 条为证）。结论：机制层面 C 级落库+回填**已闭环**，真实缺口是「靠 agent 自觉、无成文 SOP 与漏记核查例程」——这正是父卡该交付的 SOP 文档的正当性所在，但父卡描述中「当前只观察不落库导致样本流失」的前提陈述与事实不符，应修正为「已落库但依赖自觉、需 SOP 固化与核查」。
