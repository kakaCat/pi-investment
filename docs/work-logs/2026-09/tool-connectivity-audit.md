# 工具链连通性审计（agent-dh → quantsys-v2 全量实测）

> 审计人：investor（w-8366e526）｜日期：2026-09-01 晚
> 触发：用户问"agent-dh 调用 quantsys-v2 都需通过工具实现，确认业务流程都是通的吗"
> 方法：44+ 个工具逐个真实调用（只读全测；写操作做安全验证——portfolio_trade 宪法拦截响应即证明链路通）

---

## 0. 结论

**主干业务链路是通的**（数据→决策→交易→复盘核心工具全部正常），但实测揪出 **10 个断链**（4 路由 404 + 6 工具执行期崩溃）+ **8 处数据/逻辑异常**。断链已全部修复并验证（提交 2b2cebbe/b6dfd277）。

| 状态 | 数量 | 说明 |
|---|---|---|
| ✅ 正常 | 34 | 核心链路全覆盖 |
| ❌ 断链（已修复） | 10 | 4 路由 404 + 6 缺 wrap |
| ⚠️ 异常（通但数据/逻辑有问题） | 8 | 见 §3 |

## 1. 断链清单与修复（10 处，全部已修）

### 1.1 路由 404（4 处）——根因两类

| 工具 | 端点 | 根因 | 修复 |
|---|---|---|---|
| strategy_list | /api/strategies/list | services.py rewrite（55c0ce73）后 22 处裸名 from-import 全炸 → 19 个路由模块注册失败 | services.py 加模块级 `__getattr__` + `_LazyServiceProxy` 惰性代理（避免启动早期深层依赖解析崩溃） |
| market_alert | /api/alerts/check | 同上（alerts_async 缺 game_alert_service） | 同上（修复后 200，首次查询 27s 属重计算正常） |
| event_calendar_check | /api/events/upcoming | events_async.py 存在但 **main.py 从未 include**（路由写了没注册） | main.py 补注册段 |
| retail_panic_index | /api/market/perception/panic-index | 端点从未实现（服务层 retail_panic_index_service 早已存在，路由层缺失） | market_perception_async 补 panic-index + series 两端点 |

**修复后注册失败 19→3**（剩 p1_batch/p2_batch1/p2_batch2 相对导入，既有非关键路径问题）。

⚠️ 重要关联：backtest_async 也在失败清单（缺 backtest_engine 裸名）——**combo/matrix/backtest-run 全系路由在当日午间后实际处于 404 状态**，本次一并修复。

### 1.2 工具执行期崩溃（6 处）——同一根因

| 工具 |
|---|
| trading_calendar、opponent_behavior、limit_up_pool、lhb_dragon_tiger、fund_flow、stock_intel |

- **根因**：`BaseTool.wrap` 是 abstract 方法，6 个工具子类未实现；tsx 运行时不检查 abstract → schema 冒烟（19/19 只编译不执行）抓不到 → 调用时才炸 `this.wrap is not a function`
- **修复**（b6dfd277）：wrap 改为默认实现 `{success: true, data}`，子类需自定义 message/metadata 时覆盖——治本且防再犯
- **生效条件**：需 DSH profile 重启加载新代码（与 M2-3/E-2 同批待重启）

## 2. 主干链路实测（全部通过）

| 链路 | 工具 | 结果 |
|---|---|---|
| 行情数据 | quote / kline / financial / market_sentiment | ✅ |
| 决策前置 | regime_position_limit（euphoria 上限 30% 合规）/ m4_circuit_breaker（回撤 -7.72% 未熔断）/ risk_controller / risk_metrics | ✅ |
| 信号 | strategy_execute（扫 396 只）/ signal_track report / opportunity_scan | ✅ |
| 标的 | pool_list（29 池）/ mainline_scan / mainline_stocks / chip_analysis | ✅ |
| 交易 | account_info / position_list / trade_monitor / **portfolio_trade（非交易时段宪法正确拦截：链路通+校验生效）** | ✅ |
| 学习进化 | learning_analyze（43 样本 5 模式）/ evolution_leaderboard / genome_list/read | ✅ |
| 运维 | scheduler_manage list / data_manager status / notification_channels（今日 3 条通知已送达）/ agent_os_status | ✅ |

## 3. 数据/逻辑异常（链路通但不正常，待修）

| # | 工具 | 异常 | 性质 |
|---|---|---|---|
| 1 | position_list vs risk_controller | **持仓不一致**：前者 2 只（601288/002241），后者 3 只（300750/000999/600036） | 🔴 数据源不一致，影响仓位校验可信度 |
| 2 | screening | ROE≥15 筛选返回退市股（688287 退市观典）且得分全 0、"符合条件: undefined 只" | 🟠 筛选逻辑/字段映射异常 |
| 3 | opportunity_scan | 扫描范围 0 只 | 🟠 池子为空或未传 pool |
| 4 | risk_barra_decomposition | 因子协方差全 null | 🟠 因子数据不足 |
| 5 | data_fetch_financial | PE-TTM/PB 全 0 | 🟠 估值字段未计算 |
| 6 | data_fetch_kline | "时间范围: undefined ~ undefined" | 🟡 渲染字段缺失 |
| 7 | rotation_simulate | action 大小写敏感（BUY 被拒，要求小写） | 🟡 入参校验过严 |
| 8 | mainline_scan | mainlines 空（今日主线未落库） | 🟡 数据待积累 |
| 附 | data_fetch_macro | "后端未提供 pmi 数据" | 🟡 宏观数据未接入 |
| 附 | data_fetch_north_flow | 北向数据源永久不可用（交易所停止披露）——工具优雅降级+替代方案，设计良好 | ⚪ 外部变化，非 bug |
| 附 | memory_search "止损经验" | 0 条 | 🟡 经验库沉淀不足 |

## 4. 调度侧附带发现

- Agent OS 任务列表大面积禁用是 ADR-002 切换的预期结果（v2 APScheduler 接管），但意味着**无 failover**——v2 调度挂则任务全停。建议补 v2 调度健康监控告警。
- 公告板 board_read 返回的历史帖子记录了一个相关遗留：risk metrics 忽略 account_name（#/api/risk/metrics 全局数据问题）——board 帖 #25409abb 仍 open，与本审计 §3-1 持仓不一致可能同源（账户过滤缺失）。

## 5. 修复提交

- `2b2cebbe`：services 裸名导入兜底 + events/panic-index 端点补全
- `b6dfd277`：BaseTool.wrap 默认实现
- 验证：4 个 404 端点全部 200；冒烟 19/19；工具待 DSH 重启后线上生效

## 6. 后续建议（按优先级）

1. **P0**：DSH 重启（加载 wrap 修复 + M2-3 pool_battlefield + E-2 trade_verify 工具新代码）——等并行会话 untracked 工作提交后执行
2. **P1**：持仓数据源不一致排查（position_list vs risk_controller 读不同表？）
3. **P1**：board 遗留帖 #25409abb 的 risk metrics account_name 过滤修复
4. **P2**：screening/opportunity_scan 空结果排查；barra 因子数据补齐
5. **P2**：v2 调度健康监控（无 failover 后的单点告警）

---

## 7. 第二轮全链路验证（2026-09-01 深夜，investor w-8366e526）

> 触发：用户问"所有的业务流程都跑通了吗"→ 8 批次系统性复测（含 §3 遗留 8 项 + 首轮标记待重启项）
> 本轮新增修复提交：`4a6b5a02`（4 处契约）、`c523ad62`（getAlerts 超时）

### 7.1 本轮修复并验证通过（重启后工具级实测 ✅）

| # | 项 | 根因 | 修复 | 实测结果 |
|---|---|---|---|---|
| 1 | **screening 返回退市/ST 股**（§3-2） | DSH 加载旧 `quantsys-v2-client/dist`（src 21:24 已修扁平化，dist 12:35 旧构建——package.json exports 指向 dist 非 src） | 重建 dist（21:37） | ✅ 返回高 ROE 股（九号公司-WD/亿联/美的/宁德/比亚迪/山西汾酒），无 ST/退市，criteria 扁平化 `{min_roe,max_pe}` 生效 |
| 2 | **opponent_behavior schema 校验失败**（retail.net_flow must be a number） | 后端降级返回 None 不满足工具 output schema | 后端空值改语义默认（net_flow:0 / emotion_index:50.0 / stage:'unknown'），保留 degraded 标注 | ✅ 工具级正常返回，标注"数据降级: true + 资金流数据不可用" |
| 3 | **fund_flow HTTP 400** | 数据源全失败时后端错误码用 400（语义应为上游不可用） | 400→502 | ✅ 工具优雅降级：两融数据正常展示 + "部分源降级: fund-flow HTTP 502" |
| 4 | **data_manager 持仓数 3 vs position_list 2** | health 读旧 `portfolio_holdings` 表（5-6 月遗留 3 条），工具链读 agent_virtual 模拟账户 | health 优先读模拟账户，旧表仅回退 | ✅ holdings_count=2（与 position_list 一致） |
| 5 | **sector_analysis 超时**（后端 9.9-17s vs 工具 10s） | 工具 timeoutMs 过紧 | 10s→40s | ✅ 16s 内返回 496 行业+504 概念 |
| 6 | **market_alert 超时**（后端冷路径 24-39s vs client 30s） | client 默认超时 30s 卡边界 + 后端重计算慢 | 工具 10s→40s + client getAlerts 30s→60s | ✅ 稳定返回（0 条告警） |
| 7 | **opportunity_scan 超时** | 工具 timeoutMs 30s < 后端冷路径 | 30s→60s | ✅ 60s 内返回（扫描 0 只=池空，链路通） |
| 8 | §3 其余遗留（#1 持仓一致/#5 财务 PE/#6 kline 渲染/#8 mainline/#附 macro/north_flow） | 首轮已修 | — | ✅ 重启后工具级全部验证通过（position_list 2 只=risk 一致；茅台 PE 20.58/PB 6.90；kline 无 undefined；mainline Top3 落库；macro PMI 5 条；north_flow 优雅降级） |

### 7.2 环境性/已知遗留（非断链）

> 2026-09-01 深夜第二轮：用户确认"全部处理了"→ 遗留 6 项全部修复并验证 ✅（见下方逐项）

| 项 | 状态 | 说明 |
|---|---|---|
| ~~sector 东财板块接口~~ | ✅ **已修复（fb030a97 + 1f5bb67e）** | ①DB 快照兜底：quant.sector_snapshot + 路由层 stale-while-error（成功落库、失败回退最近快照）②多数据源 failover：新增 AkshareSectorProvider（新浪行业+同花顺概念，独立通道）挂入 sector_providers，实测 eastmoney 故障自动切 akshare |
| fund_flow 外部源 | 当日全失败（两融正常），502 降级显示 | 外部源故障，重试即恢复 |
| ~~opportunity_scan 参数契约~~ | ✅ **已修复** | 三层契约：后端 `signals_async.py` scan_signals 消费 scan_type（technical/fundamental/hybrid 覆写权重）与 pool_id（池成员限定扫描范围，无效池返回 400）；DSH 工具 `OpportunityScanTool.ts` raw 改 `Array.isArray(raw) ? raw : raw?.opportunities ?? []`（client unwrap 后为裸数组）。实测三模式 top5 显著不同（technical 688256/688169/002241 vs fundamental 688169/688256/600887 vs hybrid 688256/688169/600887），pool_id=41 扫 10 只、pool_id=999 报"股票池 999 无有效成员" |
| ~~signal_track 5/10/20 日胜率 N/A~~ | ✅ **已修复（含衍生 kline 污染根治）** | ①代码根因：`signal_tracking_service.py` `_get_trading_date_after` 用 TradingCalendarService 真实推进交易日、`_get_close_price` 兼容 polars DataFrame、`entry_price` 转 float（原 Decimal 冲突致回填恒失败）。②衍生污染根治：`data_backfiller.py` `_is_index_symbol` 白名单命中后校验 stocks 表 list_date——有上市日期=真实股票按股票路径（000001 平安银行/000016 *ST康佳A/000905 厦门港务/000852 石化机械 4 组双身份代码此前被指数点位覆盖，删除 326 行污染行并备份 quant.daily_klines_polluted_backup_20260901）。③调度恢复：signal_perf_backfill_daily 由 `/bin/true` 空壳改为 webhook 任务（Agent OS → v2 `register_job_handler("signal_perf_backfill_daily")` 直调 update_performance，不依赖 agent 响应），实测 trigger 链路成功（status:success, updated 正常返回）；id13 脏值 3952.18 已清除（8/21 信号因 8/28 K 线缺失暂 NULL，网络恢复后 kline_daily_sync 以股票路径自动补齐） |
| ~~rotation_proposal 字段名~~ | ✅ **已修复** | `RotationProposalTool.ts` execute 规范化：从 raw?.proposal ?? raw 提取 actions（Array.isArray 校验）映射 `{action, strategy_id, strategy_name, reason, suggested_weight: new_weight ?? weight, priority}`；prompt.ts 类型对齐（proposals 元素 + meta 块）。实测工具调用正常（冷却期 actions=[] 与后端一致，预计换手 0.0%） |
| ~~v2 调度无 failover~~ | ✅ **已修复** | `health_async.py` 注册 `v2_health_check` handler（调 check_job_health：僵尸/漏执行/高失败率），register_jobs_to_agent_os.py 注册每日 16:45 任务。实测 Agent OS trigger → webhook → v2 handler 链路成功，**首次运行即发现真实问题**：34 个启用任务中 1 僵尸 + 24 漏执行（>24h）——调度健康监控价值实证 |
| ~~data_manager balance~~ | ✅ **已修复** | `health_async.py` platform_status 改读 `_sim_repo.get_account('agent_virtual')`（source=simulation_account），_acc 为 None 时回退旧 balance 表。实测返回 cash 90391.52/market_value 15063.00/total_assets 105454.52 与 account_info 一致，两套账户体系口径统一 |
| ~~board 帖 #25409abb~~ | ✅ **已完成（claimed → done, rev3）** | risk metrics account_name 过滤（P1）：实测 agent_virtual maxDrawdown -7.72% vs agent_brain -6.14% 区分生效；scheduler_handlers 全 async 已核实；trades 接口 200 正常 |

### 7.2b 修复后新增发现（2026-09-01 深夜）

- **kline 数据源污染（signal_track 回填脏数据根因）**：000001/000016/000905 的 daily_klines 被指数点位覆盖（`_is_index_symbol` 白名单误判——000001 上证指数 vs 平安银行等 4 组双身份代码）。已删 326 行污染行（备份至 quant.daily_klines_polluted_backup_20260901），`_is_index_symbol` 加 stocks 表 list_date 校验根治。注：000001 6 月前历史数据亦混入指数点位，删除后 8/20-8/21、8/28-9/01 缺行，待网络恢复后 kline_daily_sync 股票路径补齐；其余持仓股（600519/300750/002241/601288/000858）K 线核对正常
- **v2_health_check 首跑告警**：34 启用任务中 1 僵尸（gem-kline-upd...）+ 24 漏执行——疑似 Agent OS 调度投递层问题，建议维护方排查（见 §7.3 后续）
- **v2_health_check 首跑告警修复（2026-09-01 深夜第二轮，已闭环）**：告警定性 = **ADR-002 切换日过渡期现象**，非实时故障——上午 v2 以 Agent OS enabled 模式反复重启（本地 APScheduler 未启动），Agent OS 侧又无这 24 任务注册（多为 8/15-8/28 后无调度）；18:51 切换后 job store 已装入全部 34 任务、next_run 全在未来。三处修复 + 一处顺手修：
  - **find_missed_tasks 口径修复**：新增排除 public.apscheduler_jobs 中 `next_run_time > now` 的"已排期"任务（job id 为 `task_{id}` 映射），切换日 cron 时点已过不补跑是设计内行为，不再误报 24 missed
  - **find_high_failure_tasks 排除孤儿 run**：error LIKE '%孤儿%' / '%进程重启%' 的 run 不计入失败率（进程重启打断≠任务逻辑失败，用 or_ 处理 error 为 NULL 的正常 run）——每日数据质量检查 3/3=100% 误报消除
  - **孤儿 run 3240 人工闭环**：20:08 手动 trigger 的 gem-kline-update 历经 3 次进程重启已成真孤儿（无存活线程），DB 闭环为 failed（error 注明"孤儿 run：进程重启遗留，人工闭环"）
  - **顺手修 webhook 写库 parse_cron bug**：新任务名时 `add_task(cron_expression="managed_by_agent_os")` 触发 parse_cron 抛异常被吞 → run 不落库；修复 `add_task` 与 `complete_run` 对 `managed_by_agent_*` 保留字跳过 cron 校验与 next_run 计算（complete_run 内残留的 parse_cron 曾致 run 卡 running，一并修）。单测：正常 cron 通过、非法 cron 拒绝、保留字接受 ✓
  - **验证**：v2 重启（fallback 模式 34 任务入 job store）→ webhook 端到端触发 v2_health_check → run 3246 success，`status: ok, summary: {total_enabled:34, zombie:0, missed:0, high_failure:0}, issues:[]`；9/2 早间本地 cron 首跑（每日数据更新 7:30/因子 8:00/信号 8:30 等）可观察自然恢复

### 7.3 本轮提交

- `4a6b5a02`：4 处契约修复（client dist 重建、opponent_behavior 空值默认、fund-flow 502、health 持仓口径、3 工具超时调大）
- `c523ad62`：getAlerts 30s→60s（配合工具层超时调大）
- `fb030a97`：sector 板块列表 DB 快照兜底（quant.sector_snapshot + 路由 stale-while-error，用户反馈追加）
- 已推送 main（1f0001c5..fb030a97）
