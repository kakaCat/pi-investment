# 投资脑闭环补缺：评分口径 / 余量感知 / 候选猎取（2026-09-13）

- 执行窗口：**w-c8cae280**（investor / 投资脑）
- 起因：用户问「投资脑自营盘还缺什么能力」，随后同意「先做 A（开闸）+ C（自知）」
- 结论：**零件齐、装配缺**——入料端（选股）与出料端（下注）都是空的，中间的风控/复盘很密

## 一、A 开闸：侦察后发现原方案不成立（诚实修正）

原计划「打开 pre-market-scan 全市场扫描」经代码核查**不成立**：

quantsys-v2/infrastructure/scheduler/scheduler.py:1299 的 _handle_market_scan_preopen 是**空实现**——
只 list_all_active 取股票列表，循环体是 pass（注释写着 "Simplified scan logic - extend with actual analysis"），
循环上限 stocks[:10]，返回 opportunities_found: 0。**开闸也产不出任何候选。**

同时确认的其它事实：

1. 19 个 prompt 驱动的调度任务里，调用 opportunity_scan / pool_* / screening / strategy_execute 的数量**全部为 0**；
2. v2 侧唯一在跑的信号生产是「每日信号生成」（工作日 08:30），params 硬绑定 strategy_ids=[179,178,163,193]——
   这四个策略在 strategy_list 里全是 status=error，正是 732 条 confidence 全 NULL 信号的来源（R-011 已判不可用）。
   该任务属**策略线**，不归投资脑，本次未改动，仅记录；
3. 池信号扫描能力已实现（PoolSignalScanner + stock_pools.last_signal_scan + POST /api/pools/{id}/scan-signals），
   但没有任何调度调用它；旗舰动态池「低估值蓝筹股」(pool 3, scan_enabled=t) 的 last_signal_scan = **never**；
4. 候选池成员无买卖点：全市场候选池_v1 (pool 35, 50 只) 成员全部 buy_point/sell_point = null、tags 空。

**替代方案（已落地）**：新建投资脑专属例行 **agent-brain-candidate-hunt**（工作日 08:45，owner=investor，
agent_line=account，webhook :13080/agent-os-trigger，metadata: watchdog=auto_rerun + catchup 3h/check_after 09:30/market_hours），
把「选股 → 候选 → 买点 → 触发条件 → 建议金额」做进日常循环，**只落计划不下单**（下单仍由盘中例行按 R-009 与宪法执行）。

## 二、C 自知：两个真实缺陷已修

### C1 成交决策永远进不了评分（大小写口径不一致）

- 现象：SCORABLE_TYPES = {trade_buy, trade_sell, missed_opportunity}（小写），而
  account_trading_service._auto_record_decision 写 f-trade_{action}（action 为 BUY/SELL 大写）
  ⇒ 落库成 trade_BUY / trade_SELL，**结构性不可打分**；
- 实证：quant.agent_decisions 中 pending 的 trade_BUY × 4 + trade_SELL × 4 共 **8 条**永不进入评分；
  agent_brain 的 DEC-20260911112419-a07cbe59 (trade_SELL) 就挂在那；
- 修复：写入端统一小写 + 读取端 str.lower() 归一（历史大写记录一并复活）；
  新增回归测试 test_uppercase_trade_type_scored → tests/services/evolution/test_decision_score_service.py **9/9 通过**；
- 提交：**7eb399de**

### C3 position_size 不读 regime 余量（把余量当空气）

- 现象：risk_controller(position_size) 恒返回 recommendedSize = totalValue × 20%（实测 20000，accountValue 写死 100000），
  不读 regime 上限与当前敞口——agent_brain 敞口 14.2%、上限 40%、余量 25.8pp 时仍建议按 20% 硬顶满仓单只；
- 修复：叠加余量钳制「可下上限 = min(单股 20% 硬顶, regime 剩余可加仓金额)」，并返回
  staticRecommendedSize / headroomPct / headroomAmount / cappedBy / regimeCapPct / currentPositionPct；
  数据降级收紧到 60%（R-006），无 regime 记录时显式提示，余量校验异常降级不阻断；
- 测试：新增 tests/risk-position-size-headroom.test.ts **6/6 通过**（余量充足 / 不足 / 已超限 / 降级收紧 / 无记录 / 异常降级 六态）；
- 提交：**79755596**

## 三、验证记录

| 项 | 结果 |
|---|---|
| 决策打分测试 | pytest tests/services/evolution/test_decision_score_service.py **9/9** |
| 风险工具测试 | vitest risk-position-size-headroom **6/6**；account-guard **17/17** |
| 插件 schema 冒烟 | **19/19** |
| risk dist 构建 | dist/index.mjs 40.09 kB ✔ |
| v2 服务重启 | quantsys_v2_restart → pid 14714，6 秒健康就绪 |
| 新例行在册 | scheduler_manage list = 28 个任务，agent-brain-candidate-hunt enabled，cron 0 45 8 * * 1-5 |

## 四、遗留

1. agent-brain-candidate-hunt 首次真实运行 = **2026-09-14（周一）08:45**，需收盘后核对产出质量（是否真产出带买点的候选，有没有变成「每次都无候选」的空转）；
2. risk 插件改动需 **:13080 重启**才生效（按上次同款方式：脱离进程组的延迟自动重启）；
3. 策略线问题（每日信号生成绑定 4 个 error 策略、20 个策略 0 健康、pre-market-scan 是空实现）**不归投资脑**，仅记录；
4. 池成员仍无买点/卖点元数据——候选猎取例行目前靠 watch 规则承载「触发条件」；若要池化下注计划，需要给池成员补 buy_point（可后续做）。
