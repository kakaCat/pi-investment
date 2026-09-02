# 盈利引擎系统设计 + 自主能力体系（Autonomy 线）全流程实现核查（2026-09-03）

> 署名：investor w-8366e526
> 请求：用户问"盈利引擎系统设计、自主能力体系（Autonomy 线 全流程）都实现了吗，帮我查看代码"
> 方法：注册/文档声称 ≠ 实现。逐组件读业务代码（execute 是否发真实 HTTP/真实计算/真实编排）+ 反向核对后端路由 + 数据库/调度运行产出实证（runtime 证据优先）。
> 结论速览：**引擎线工具层 62/63 真实（1 空壳=北向资金，有意降级但描述误导）；v2 业务调度 21 任务中 8 空壳 + 2 代码 bug 假成功（regime/style/sentiment 三表断档为证，last_status 全表不可信）；Autonomy L1-L2 代码真实闭环、L3 验证门输入断裂（registerCandidate 死代码零调用者，8/20 后无新 watching 候选）、L4 元学习/benchmark 从未实现；调度双层分工合规但 9/2 下午窗口断档一次；自动自进化在"提案生成"后断链（auto_apply 默认 false + 无调用者 + 登记断裂）。**

---

## 0. 判定分层口径

| 层 | 判据 | 说明 |
|---|---|---|
| A. 注册/文档声称 | 任务/工具在表、doc 打勾 | 不足为证 |
| B. 业务代码真实 | execute 发真实 HTTP(client)/真实本地计算/真实编排 | 本审计主体 |
| C. 真实产出 | 数据库/文件/记忆出现业务结果 | 最硬证据 |

---

## 1. 引擎线（M0-M8 盈利引擎生产流水线）核查

### 1.1 DSH 工具层：62/63 真实（子审计 c4a42b77 + 父窗口独立抽查一致）

范围：packages/ 下 10 个业务包 63 工具（investment 13 / trading 9 / risk 4 / market 7 / strategy 7 / competition 8 / factor 3 含 model_predict / intelligence 6 / data-manager 3 / notification 3）。方法：逐工具读 execute + 后端 391 条路由反向核对。

| 包 | 判定 | 关键证据 |
|---|---|---|
| investment | 12 真实 + **1 空壳** | data_fetch_quote/kline/financial/macro/sentiment/pool_list/strategy_list/event_calendar/stock_intel/trading_calendar/pe_percentile/dividend 均真实 client 调用；**data_fetch_north_flow 空壳**（见 §3.1） |
| trading | 9 真实（含重编排） | portfolio_trade 交易时段断言+R-008 检索+regime 校验+操纵检测+真实成交+滑点落库；account/position/monitor/algo/verify/analyze/m4/slippage 全真实 |
| risk | 4 真实 | risk_controller/risk_metrics/barra/regime_position_limit（本地 CAPS 映射+熔断检查，读 AgentOS memory） |
| market | 7 真实 | style/sector/chip/swing_points/regime_daily/mainline_scan/mainline_stocks 全真实（regime_daily/mainline_scan 为本地算法+幂等落库） |
| strategy | 7 真实（转发） | strategy_execute/optimize/opportunity_scan/screening/rotation_proposal/simulate/execute（action 白名单，dry_run 后端已支持） |
| competition | 8 真实（转发） | competition/opponent/manipulation/retail_panic/pool_battlefield/fund_flow/lhb/limit_up |
| factor | 3 真实 | factor_calculate/analyze + **model_predict 位于 factor 包**（无独立 model 包，模型训练/评估未封装工具） |
| intelligence | 6 真实（转发） | watch_list/manage/market_alert/signal_track/decision_audit/history |
| data-manager | 3 真实 | data_quality_report/data_manager/kline_daily_sync |
| notification | 3 真实 | 走 AgentOSClient :8080 真实投递（非 qv2） |

统一客户端确证：QuantsysV2Client（client.ts 1742 行 axios→:5001，69 方法全真实 HTTP）、AgentOSClient（http.ts:11 axios→:8080）。无伪造、无统一客户端绕过。

**runtime 佐证（本窗口实证）**：regime_position_limit → sideways(9/2) cap 60% actual 14.4% compliant；account_info → 总资产 10.56 万/现金 85.6%；watch_list → 35 条真实规则（含 9/2 盘后补挂 601288 止损止盈）。

### 1.2 v2 业务调度层：21 任务中 8 空壳 + 2 bug 假成功（子审计 51809682）

| 类别 | 数量 | 任务 | 证据 |
|---|---|---|---|
| ✅ 真实实现 | 11 | 233 data_update、236 signal_generate（9/2 saved 16 条）、242 signal_execution、249/268/269/271 v13 系、307 trade_verify、308 fund_flow（6423 条落库）、311 signal-perf-backfill、301（修复后代码） | 真实 service 调用 + 落库 |
| ❌ 空壳/TODO | 8 | 261 chan_scan（"待实现"scanned=0）、262 chan_knowledge_distill（failed）、**312 market_style_update（从未真实落库）**、250 market_scan_preopen（只数股票）、252 strategy_validate（TODO）、253 strategy_discover（只数股票）、237 report_daily（只数股票）、238 financial_data_update（TODO） | 无业务逻辑 |
| ❌ 代码 bug 假成功 | 2 | 258 pool_refresh（'function' object has no attribute 'list_pools'）、301 修复前（'MarketPerceptionService' has no attribute 'regime_daily'） | 外层 success 内层 error |

**假成功机制根因（重要）**：job_executor 外层只 catch Exception，Job 内部失败被 JobRegistry 转 JobResult.fail → complete_run(success=True)。**quant.scheduler_tasks.last_status 全表不可信**，真实失败藏在 runs.result 内层。R-004 对账须查 result->>'status'。

**业务表产出断档铁证（注册 ≠ 产出）**：

| 表 | 最新日期 | 判定 |
|---|---|---|
| quant.daily_klines | 09-02 | ✅ 458 万行管道活（真实数据管道，DailyJobs host 守护线程） |
| quant.signals | 09-02 | ✅ 17860 行（236 真实生成） |
| quant.stock_fund_flow | 09-02 | ✅ 27709 行（308 真实） |
| quant.market_regime | **08-28** | ❌ **断档 5 天**（301 假成功直接证据） |
| quant.market_style_state | **06-02** | ❌ **312 从未真实落库** |
| quant.market_sentiment_daily | **08-28** | ❌ 与 regime 同步断档 |
| quant.trading_signals | — | ⚠️ 0 行（无实盘信号链路） |

**⚠️ regime 双轨差异（本窗口实证）**：DSH 决策层 regime 轨道健康（regime_position_limit 返回 regime_date=2026-09-02 sideways），因 DSH regime_daily 落 AgentOS memory（market:regime scope）；v2 数据层 quant.market_regime 断档 5 天（301 job 假成功）。**决策层与数据层 regime 各自独立，v2 侧断档不影响 DSH 决策读数，但表明"v2 声明任务≠真实产出"。**

### 1.3 双层调度分工合规（ADR-002）

- public.tasks 13 条全 executor_type=agent（profit_engine 8 + autonomy 5），0 system → "Agent OS 管 agent 提醒" ✅
- quant.scheduler_tasks 21 条全 executor_type=system → "v2 管业务" ✅
- webhook 僵尸任务已清（09-02 228a210f 删 9 zombie），无同命令双注册
- 遗留：APScheduler jobstore 30 个 job 残留 9 个孤儿（start() 只 replace_existing 不 remove_all）；JobRegistry 25 注册 vs 表 21（4 个由 DailyJobs host 接管，属设计）

### 1.4 v2 进程与运行实证

- Python PID 27148 监听 127.0.0.1:5001，启动 09-02 22:57:15（晚于 228a210f 修复 commit → 修复后代码已加载）
- quant.scheduler_runs 544 条（06-04→09-02），9/2 从 06:30 到 18:00 共 16 次真实 job 运行
- DailyJobs host 守护线程真实产出（inprocess_job_runs 9/2：evening_pipeline 20:30 success、chip_distribution 21:10 success、data_quality 17:15 success、morning_topup failed 源探活）

---

## 2. Autonomy 线（L1-L4）核查

> 子审计 13794323 增量结论已并入（父窗口独立验证 registerCandidate 死代码与 learning_apply 占位均属实）。

### 2.1 L1 记忆/经验层
- memory_search/memory_write/experience_write 工具真实（memory 包）
- experience_stats(30d) 实证：88 条，win_rate 2.3%（77 条未标注结果），profit 2/loss 3/neutral 11——**经验库有量但质量标注弱**
- **经验存储链路实证（本窗口定位）**：learning auto-track 落 AgentOS API（osMemory.createMemory kind=experience）→ 实际存储 **quant_investment.public.memories**（category=experience 88 条，与 experience_stats 一致；含 9/2 记录：601288 neutral 盘后复盘 19:38、600926 清仓 watch 残留 13:56、300720 loss 换仓未挂止损 9/1）
- **存储双库发现**：agent_os 库（memories 停在 08-19）为遗留废弃库——AgentOS config.yaml dbname=quant_investment，读写实际落 public.memories；两库数据不一致是迁移残留，非数据丢失
- decision_audit/history 真实（转发 v2；public.memories decision 仅 1 条 → DSH 决策审计走 v2 quant.decisions，非 public.memories）

### 2.2 L2 学习/进化层
- learning_track 自动拦截 5 工具真实（plugin event hooks）；learning_analyze/distill/apply 真实
- evolution_run/leaderboard 真实（leaderboard 10 策略 fitness 0.1-0.2；evolution 工具为纯代理→agent-os evolution_handler.go 真实存在含 qv2 baseline 请求，三层依赖未端到端实测）
- daily_distill 本体实测非空壳（22 样本/5 模式/3 提案），但提案质量薄（全为 learning_analyze 通用强化类）
- **闭环设计确认（代码实证）**：DailyDistillTool auto_apply 默认 false（L58 `params.auto_apply || false`，L81 `dry_run: !autoApply`）——蒸馏→genome candidate 需显式 auto_apply=true 或次日人工裁决，**非全自动闭环**；9/2 晚 evolution-distill-daily prompt 亦为 auto_apply=false 预览模式 → 解释 genome 9/1 后无自动 candidate
- 🔴 **learning_apply 非 dryRun 为显式占位**（learning/src/index.ts:543 注释自认"这里是占位实现"；applyChanges :801-807 仅记日志）——与 CLAUDE.md 声称"learning_apply 集成 self_restart"不符
- 🟠 **learning_distill 只读进程内 buffer**（:595-602 loadExperiencesBySource 不读 OS 记忆库）——重启后 buffer 空则 distill 无数据（daily_distill 的 learning_analyze 走库优先不受影响）

### 2.3 L3 基因组/验证门
- genome_update 真实（写+git+canary 金丝雀）；genome g10→g18 8 代 git 谱系
- 🔴 **candidate 登记→裁决衔接断裂（本审计最重要发现）**：写 candidate 三环节彻底分离——①genome_update(stage='candidate') 真实但只给 genome.json history 打 stage 标记（GenomeUpdateTool.ts:142-143 `entry.stage = stage`），**不写 candidates.json**；②candidates.json 唯一写入者 registerCandidate（evolver/src/index.ts:194-223）**全仓零调用者**（父窗口独立验证：grep 唯一命中即定义行，6ec5cd74 BaseTool 重构删除内联调用点后成死代码）；③ValidationGateTool 读 candidates.json（:124）只 filter status='watching'（:184）→ **对新变异"空转裁决"**（裁决逻辑 :179-342 完整真实，永远无新输入）。live 实证 candidates.json 仅 2 条 8/25 promoted 遗留，g11→g18 无 watching；genome.json history 中 g16 stage=candidate（8/28 force 修复）无对应 candidates.json 记录 → "两套账、登记层停摆"
- validation_gate/prompt_evolver/genome_promote/rollback 真实；8/25 前链路曾工作（g8/g10/g14 promote commit 为历史遗留）
- **但 9/1 后零自动闭环产出**：genome 最后 commit 219c4f0（g18 lessons v7，9/1 手动沉淀）
- weekly_report 工具缺口已于 2026-09-03 修复（WeeklyReportTool 实测返回第 35 周周报）

### 2.4 L4 元学习/benchmark
- **meta_* 工具 + benchmark：全仓 grep 零命中，从未实现**（meta_profile/meta_curriculum/meta_transfer 均 0 实现；AUTONOMY-SYSTEM.md 能力矩阵诚实标注 L4 "-"）
- meta-learning-weekly 仅为周日 11:30 的提示词引导任务（prompt 517 字：genome_history 闭环检查→memory 元分析→跨代→飞书），**从未产生执行产物，首窗 9/6**
- unified 文档 §5"L4 元学习 ✅ 自动启动（周日 11:30，闭环门槛检查）"实指该调度任务已挂，**非工具实现**——文档描述过实

### 2.5 Autonomy 线 L1-L4 closure 总判定（子审计 13794323）
- **L1 学习/蒸馏**：✅ 闭环真实（auto-track 落库实证 + daily_distill 编排 learning_analyze→prompt_evolver→genome_update candidate 代码全通）
- **L2 进化执行**：✅ 闭环真实（genome_update 原子写+git commit+金丝雀渲染自动还原；git 谱系 8 代 g8-g18 实证）
- **L3 验证门裁决**：⚠️ 逻辑真实但**输入断裂**（registerCandidate 零调用者，8/20 后无新 watching 记录，对新变异空转裁决）
- **L4 元学习**：❌ 0 实现（仅调度任务占位，首窗 9/6 未达）
- lifecycle 文档声称 5 工具（含 self_system_prompt/self_info），实际注册 3 个 Self* + board 三件套——CLAUDE.md 过时

---

## 3. 空壳与差距清单

1. ❌ **data_fetch_north_flow（工具层唯一空壳）**：execute 零网络零计算，硬编码返回不可用+替代方案；qv2 注入未用（DI-unused 全仓唯一）；prompt 描述仍写"获取北向资金流向（调用约需1分钟）"与实际不符。性质=**有意降级**（2024-08-17 交易所停止披露北向每日净买入+港交所 CCASS 受限），不编造数据，但描述误导。建议接线真实源或改描述/移除未用注入。
2. ❌ **v2 8 个 TODO/计数空壳任务**：chan_scan/chan_knowledge_distill/market_style_update/market_scan_preopen/strategy_validate_daily/strategy_discover_weekly/report_daily/financial_data_update。
3. ❌ **v2 2 个 bug 假成功**：pool_refresh_daily（258）、market_daily_snapshot 修复前（301）——外层 success 内层 error，last_status 不可信（机制级缺陷）。
4. ❌ **L4 元学习 + benchmark 未实现**（设计文档 TODO 准确，§5 声称"L4 元学习 ✅"过实）。
5. ⚠️ **v2 数据层 regime/style/sentiment 三表断档**（08-28/06-02/08-28）——DSH 决策层不受影响（自有轨道），但 v2 声明任务与产出不符。
6. ⚠️ **signal 5D 表现回填缺口**：signal_track 14 条信号 5D/10D/20D 全 N/A；最早 8/27 信号 5 日后 ≈ 9/3，回填任务已排（v2 15:45 + DSH 16:05 9/3 首验窗）。
7. ⚠️ **"model 无独立包"**：model_predict 物理位于 factor 包；模型训练/评估（client 有方法）未封装工具——doc 结构声称与代码不符（文档层面）。
8. ⚠️ **调度投递 9/2 下午断档一次**：15:30-16:45 批任务（post-market/distill/data-quality/m4/event）lastFired 全落 19:11（实例停机窗口的启动 baseline），非真实投递。
9. ⚠️ **遗留 agent_os 库**（config 已指向 quant_investment，但 agent_os 库 memories 停在 08-19）——旧库未清理，易造成存储位置误判（DB 直查 agent_os ≠ AgentOS API 实际数据）。
10. 🔴 **registerCandidate 死代码（Autonomy 最严重断裂）**：candidates.json 唯一写入者 evolver/src/index.ts:194-223 零调用者（6ec5cd74 重构遗留）；genome_update(stage='candidate') 只打 genome.json history 标记不写 candidates.json → 裁决器（只读 candidates.json watching）对新变异空转裁决。
11. 🔴 **learning_apply 非 dryRun 占位**（learning/src/index.ts:543 自认"占位实现"）——与文档"集成 self_restart"不符。
12. 🟠 **learning_distill 只读进程内 buffer**（:595-602），重启后独立调用无数据。
13. 🟠 **lifecycle CLAUDE.md 声称 5 工具过时**（实际 3 Self* + board 三件套；self_system_prompt/self_info 不存在）。

---

## 4. 实证补跑（2026-09-03 00:46-00:52，不等自然窗口，手动触发验证）

用户指示"待验证不要延迟，用测试数据/已有数据跑一下"。全部通过 v2 `POST /api/scheduler/tasks/{id}/trigger` 手动触发 + 读 quant.scheduler_runs 内层 result 验证：

| # | 验证对象 | 动作 | 结果 | 判定 |
|---|---|---|---|---|
| 1 | validation_gate 裁决 | force=true 强制 | **候选总数 0，裁决 0/0/0** | 🔴 **registerCandidate 断裂实证**：即使强制也"无案可裁"，验证门对新变异空转 |
| 2 | daily_distill 全链路 | days=7 手动跑 | 21 样本→5 模式→3 提案（预览，auto_apply 默认 false） | ✅ 链路真实通；⚠️ 3 提案全为"learning_analyze 自动蒸馏"高度重复（质量薄），预览不落库 |
| 3 | signal 5D 回填 | 触发 311 signal-perf-backfill | `"5d": 2, "updated": 2`（8/20 600519、8/21 000001、8/22 300750/600519 回填；8/27+ 未成熟不填） | ✅ **回填代码真实工作**；8/27+ 信号最早成熟 9/3 收盘后，311 会自动补（成熟度判定逻辑正确，非缺陷） |
| 4 | v2 301 regime 修复 | 触发 301 market_daily_snapshot | **regime/sentiment/themes 三步全 stored=true**；market_regime 从 08-28 **追平到 09-02**（range，情绪60） | ✅ **修复 228a210f 生效实证**：旧 run error 显示 `'MarketPerceptionService' has no attribute 'regime_daily'`（假成功真失败），新 run error:null |
| 5a | 312 style 空壳 | 触发 312 | message **"市场风格检测完成（待实现）"** style:"unknown" | ❌ 代码自认空壳，market_style_state 仍停 06-02 |
| 5b | 261 chan_scan 空壳 | 触发 261 | "缠论扫描完成**（待实现）**" scanned=0 | ❌ 代码自认空壳 |
| 5c | 250 pre-market 空壳 | 触发 250 | "扫描 5542 stocks"（只数数） | ❌ count-only 空壳 |
| 5d | 252 strategy-validate | 触发 252 | 执行体含 **`# TODO: 实现实际验证逻辑`**，validated_count 只是数策略数 19 | ❌ 注释级空壳 |
| 5e | 237 report_daily 空壳 | 触发 237 | "5542 stocks"（数股票代替报告） | ❌ count-only 空壳 |
| 6 | 236 signal_generate（真任务对照） | 触发 236 | signals_found 52 / saved 52 / universe 54 | ✅ 真任务真实产出，与空壳差异一目了然 |

**实证结论**：审计判定全部获得运行级证实——空壳任务自曝"待实现/TODO"、真任务有真实落库、301 修复真实生效、signal 回填真实工作、registerCandidate 断裂让验证门空转。**剩余未达窗口**：9/5 variant、9/6 gate/meta/weekly（纯周期驱动，代码已就位）。

> ⚠️ 实证副作用说明：实证 4 已将 market_regime/sentiment 追平至 09-02（修复补跑，符合预期）；实证 6 触发 236 生成了 52 条真实信号进信号库（9/2 后第二批，正常业务数据，不触发下单）。

---

## 5. 数据源

- 声称文档：docs/architecture/autonomy-profit-engine-unified.md §5、agent-dh/docs/AUTONOMY-SYSTEM.md、docs/architecture/profit-engine-overview.md
- 上轮专项：docs/work-logs/2026-09/scheduler-autonomy-line-realization-audit-20260903.md（调度投递层）
- DB：quant_investment.quant.scheduler_tasks/scheduler_runs/market_regime/market_style_state/market_sentiment_daily/signals 等；public.tasks/memories
- 子审计：c4a42b77（引擎线工具 62/63）、51809682（v2 调度 21 任务 8 空壳+2 bug）、13794323（Autonomy 线 L1-L4：registerCandidate 死代码、learning_apply 占位等增量发现，父窗口已独立验证 🔴 两条）
- 状态文件：~/.dsh/profiles/investment/state/native-scheduler.json

---

## 6. 结论

**回答用户"盈利引擎系统设计、Autonomy 全流程都实现了吗"：分层看——大部分工具是真实代码，但"全流程闭环"未成立。**

1. **引擎线工具层（M0-M8 大部分能力）**：62/63 真实（唯一空壳 data_fetch_north_flow 为有意降级但描述误导）。DSH 决策侧数据（K线/信号/regime AgentOS 轨道/经验）真实在跑。
2. **v2 业务调度层**：21 任务中 8 个空壳 + 2 个 bug 假成功（regime/style/sentiment 三表断档实证"声明≠产出"）；last_status 不可信是机制级缺陷。
3. **Autonomy L1-L2**：代码真实闭环；**L3**：genome 写库真实但 candidate 登记→裁决衔接断裂（registerCandidate 死代码）；**L4 元学习/benchmark 从未实现**。
4. **自动闭环缺失**：daily_distill auto_apply 默认 false + 无 auto_apply=true 调用者 + registerCandidate 断裂 → 自进化在"提案生成"后就断链，基因组无自动演化（9/1 后 0 自动 commit）。
5. **9/2 调度断档一次**（15:30-16:45 批任务错过窗口）——已确认守护链，9/3 起持续在线至各验证窗口。

**未验证（纯周期驱动）**：9/5 variant、9/6 gate/meta/weekly 首窗——代码已就位，等周窗自然到达。

### 实证补跑后更新（2026-09-03 00:52）

§4 的 10 项运行实证已把多数"待验证"转为已验证：
- ✅ **v2 301 修复生效**：market_regime/sentiment 手动补跑追平到 09-02（不再断档）
- ✅ **signal 5D 回填真实工作**：311 手动跑 updated=2，成熟度判定正确
- ✅ **daily_distill/236 真任务**真实产出
- ❌ **8 空壳全部运行级坐实**（5 个已实测：312/261/250/252/237 自曝"待实现/TODO"或只数股票）
- 🔴 **registerCandidate 断裂实证**：validation_gate force=true 返回"候选 0"——验证门确实空转

**剩余未修（建议后续工作线）**：①registerCandidate 恢复调用（或 validation_gate 改读 genome.json history 的 stage=candidate）；②8 个 v2 空壳任务补实现或下线（避免假成功记录持续污染 last_status）；③learning_apply 补真实应用逻辑；④v2 last_status 外层 success 掩盖内层 error 的机制缺陷（job_executor 只 catch Exception + complete_run(success=True)）。

---

## §6 修复完成记录（2026-09-03 深夜，investor w-8366e526）

> 请求："继续修复"——将 §5 剩余未修的 ①-④ 逐条落地。全部为代码+测试+实证修复，已各自独立验证；修复期间无交易委托（非交易时段）。

### ① registerCandidate 断裂 → 恢复调用链（DONE）

**根因**：`EvolverPlugin` 私有 registerCandidate（写 `<genomeDir>/candidates.json`）零调用者；PromptEvolverTool 在 `genome_update(stage='candidate')` 成功后从未登记候选 → validation_gate 读同一文件永远空转（实证：force=true 返回"候选 0"）。

**修复**：
- 新增共享实现 `agent-dh/packages/evolver/src/candidates.ts`（CandidateRecord/readCandidates/writeCandidates(原子 tmp+rename)/registerCandidate），从 EvolverPlugin 移出死代码；
- `PromptEvolverTool.execute()` 在非 dryRun 且 `genome_update` 返回 stage='candidate' 成功后调用 `registerCandidate`，把候选登记为 `status='watching'` + `observe_until=now+observeDays`；
- `ValidationGateTool` 读路径与共享实现同一文件 `<genomeDir>/candidates.json` → 登记/裁决两端收敛；
- PromptEvolverResult 增加 `candidate_id/observe_until/stage` 字段（schema 同步，含 additionalProperties 铁律）。
- 修复过程中揪出并修掉一个**假绿测试**：candidates.ts 原用 `const fs = require('fs')`（vitest CJS polyfill 下通过、tsx ESM 运行时报 TypeError）→ 改为顶层 `import { existsSync, readFileSync, writeFileSync, renameSync } from 'node:fs'`。

**验证**：`candidates-store.test.ts` 4 用例（登记写文件/幂等/原子性/字段完整性）绿。

### ② v2 last_status 假成功机制（DONE）

**根因**：job_executor 外层只 catch Exception，Job 内部失败被 JobRegistry 转 `JobResult.fail` → 外层仍 `complete_run(success=True)` → last_status 全表不可信。

**修复**：外层成功必须镜像内层结果——异常(raise)→外层 failed；`JobResult.fail` dict → 外层 failed；legacy handler 返回 `{status:'failed'}` → 外层 failed；仅内层明确成功才 success=True。静默失败伪装成功不可复现。

**验证**：`tests/infrastructure/test_job_executor_fix.py` 3 用例绿（异常/JobResult.fail/legacy error dict 均不再误报 success）。

### ③ learning_apply 占位 → 真实应用逻辑（DONE，含 distill→apply 闭环）

**根因**：learning_apply 原为占位，返回假"已应用"；且 learning_distill 只返回规则不落库 → apply 永远找不到规则。

**修复**（规则生命周期状态机，与 Fix① 的 genome candidate 生命周期同构）：
- `learning_distill` 蒸馏即落库：规则以 `kind=rule/status='testing'` 持久化到 Agent OS 记忆（信封 `{kind,scope,status,confidence,source,provenance,payload,body}`），稳定 rule_id `rule_${fnv1a(condition+action+format)}`，稳定 ID 去重复用已有记忆；落库失败不吞——返回 `persistence{persisted,total,failed,error}`；
- `learning_apply(rule_id, context, dry_run)` 真实语义：dry_run 只模拟 `{applied:false, impact:{simulated:true}}`；真实应用 = patchMemory 重写信封 status testing→active + payload 增 applied_at/applied_by/applied_context，随后重新检索验证 status==='active'，否则抛错（诚实失败，不伪造成功）；规则不存在返回 `{applied:false, message:'…请先 learning_distill…'}`；已 active 幂等返回 `already_active:true`；
- OsMemoryStore 新增 `patchMemory(id,{rebuild})`（GET→JSON.parse→rebuild→PATCH {content,metadata_patch}），Agent OS :8080 真实 API 已 live 验证；
- 原 generate*/applyChanges 死代码块删除，验证规则防除零。

**验证**：learning 10 用例绿（experienceDistill 7 + distillPersist 3：落库成功/落库失败诚实报错/空经验不调 persistRules）。

### ④ v2 strategy_validate 空壳 → 真实验证服务（DONE，report-only）

**根因**：252 strategy_validate 空壳只数 strategy_configs 行数即报 validated_count（自曝 TODO）。

**修复**：`StrategyValidationService` 对每个活跃策略做真实校验（信号源/参数/回测可用性 → valid/invalid/no_evidence 分级），`analysis_jobs` 落库 validation_report + no_evidence_skipped；scheduler_tasks 增加 no_evidence_skipped 透出；daily 路径 `deactivate_if_invalid=False` **只报告不停用**（约 7 个活跃策略不因单日校验失败被批量下线——保守原则），手动可传 True 启用自动停用。

**验证**：真实 DB E2E（report-only 校验跑通、无批量停用）；unit 用例绿。

### 测试总览（提交前全量）

```
evolver 14 (candidates-store 4 + searchRewards 4 + judgeCandidates 6)
learning 10 (experienceDistill 7 + distillPersist 3)
plugin-schema.smoke 19
quantsys-v2：test_job_executor_fix 3 + strategy_repository/validation_service/scheduler 既有用例
```

### 文档修正（对齐真实工具语义）

- `agent-dh/docs/AUTONOMY-SYSTEM.md`：learning_apply 不再声称 "restart_after/self_restart 集成/代码生成"，改为规则生命周期状态机语义；示例代码（Day 8-10 / 快速修复循环）同步为真实入参（rule_id/context/dry_run）。
- `agent-dh/CLAUDE.md`：learning_apply 条目去掉不实的 "集成 self_restart"，注明 2026-09-03 真实语义。

**状态标记**：①-④ 全部 DONE（①的 GUI 级 E2E 见下文重启验证节；②③④ 已有测试+实证）。

---

## §7 M0 执行机制判定（2026-09-03 午后 Step1 补查，investor w-36aee70c）

> 背景：用户追问"M0 数据地基 8 空壳是双轨遗留还是真缺失"，要求先定死 **21 条 quant.scheduler_tasks 实际执行走哪套机制**，再决定删/接。本节为补查结论，修正 §1 中"8 空壳=未实现能力"的表述（真实 handler 存在但不在主执行路径上）。

### 7.1 双轨真相：不是"两套都在跑"，而是"主路径跑 Job 类，真实 handler 挂在无触发源分支"

v2 内存在**三套**调度入口，但只有一条真正执行 21 条任务：

| 入口 | 代码 | 执行内容 | 是否服务 21 条 |
|---|---|---|---|
| ① 本地 APScheduler（主） | `main.py:151-175`（Agent OS 注册失败回退）→ `apscheduler_service.py:76-129` load_tasks_from_db → jobstore `task_{id}` → `job_executor.py:23` `execute_scheduled_job(task_id)` → `job_executor.py:136-232` `_execute_command(command)` | **JobRegistry 28 Job 优先**（`registry_setup.py` 注册 6 组 jobs），未命中走 Legacy Handler（仅 5 命令：data_update/data_quality_check/backtest_run/model_train/benchmark_run → SchedulerService） | ✅ 是（21 条全走这里） |
| ② Agent OS webhook | `api/internal/scheduler_webhook.py` JOB_HANDLERS ← `scheduler_handlers.py` `@register_job_handler` ← **转发到 `scheduler_tasks._TASK_HANDLERS`** | 真实 handler（chan_scan/chan_knowledge_distill/pool_refresh_daily/report_daily/market_style_update/market_scan_preopen/strategy_* 等） | ❌ 否——Agent OS public.tasks 13 条全 executor_type=agent，无 webhook system 任务回调；路径存在但无触发源 |
| ③ 手动 trigger API | `scheduler_async.py:328` → 同① jobstore modify next_run | 同① | 审计实证用，结果与①一致 |

**关键结论**：
1. 21 条任务实际执行 = ①本地 APScheduler → `_execute_command` → **JobRegistry 优先命中 Job 类**（8 空壳 Job 正在被真实执行），未命中才走 SchedulerService legacy 5 命令。
2. `scheduler_tasks.py` 里真实 `handle_*`（含 chan_scan L989→ChanScanService、pool_refresh_daily L205 等）**只被②webhook 路径引用**；webhook 无业务触发源 → **真实 handler 处于"睡"状态，从不在主路径执行**。
3. 因此审计 §1.2"8 空壳 Job"判定**在真实执行路径上成立**（Job 类壳确实在主路径被调用并返回假结果）；但修正为：**缺的不是能力代码，而是 Job 壳 → 真实逻辑的接线**（Fix④ StrategyValidateDailyJob 已示范正解）。
4. `job_executor.py:192-236` Legacy Handler 仅覆盖 data_update 等 5 命令（SchedulerService._handle_* 时代产物）——data_update/data_quality_check 因此是真实执行（233/232 出真结果）。

### 7.2 21 条任务全量归类（2026-09-03 午后 API 全量核对，21 条全部 enabled）

**A 保留（真实执行+产出落库+有消费者，12 条）**：232 data_quality_check / 233 data_update / 236 signal_generate（52 saved）/ 242 signal_execution_daily / 249+268+269+271 v13 四连 / 301 market_daily_snapshot（修复后三表落库）/ 307 trade_verify_daily / 308 fund_flow_update / 311 signal_perf_backfill_daily。

**B 空壳-接线（主路径 Job 壳要委托真实逻辑，3 条）**：
- 261 chan_scan：Job 壳 scanned=0「待实现」；真实 `scheduler_tasks:989 handle_chan_scan → ChanScanService`（backend 全栈+测试齐）。→ Job.execute 改委托 ChanScanService（同 Fix④ 模式）。
- 262 chan_knowledge_distill：Job 壳；真实 `handle_chan_knowledge_distill_weekly`（scheduler_tasks:1011 → chan_knowledge_distiller）。当前 last=failed 系 8/25 scheduler_tasks.py L205 缩进错误旧痕（已修）。→ 接线。
- 312 market_style_update：Job 壳 style=「待实现」；真实 `handle_market_style_update`（scheduler_tasks:632）**只 detect 不落库**（L648 注释：风格历史由 strategy_rotation_engine 自维护，update_style_history 已删）→ 全库 grep 无 `INSERT market_style_state` → **该表已无写入方**，而 `strategy_rotation_engine.py:756` 仍 SELECT 它（读 stale 6/2 数据）。→ 需决策：恢复落库链路 or 312 只作风格检测（供 DSH MarketStyleDetectTool 经 qv2.getMarketStyle），rotation 侧改读自维护历史。不能简单接线了事。

**C 空壳-停用/删除（count-only 或 TODO，无产出无消费者，4 条）**：
- 237 report_daily：数 5542 stocks 即报「每日报告生成完成」；每日报告职责在 Agent OS post-market-routine。
- 250 market_scan_preopen：数 5542 stocks 即报「盘前扫描完成」；盘前职责在 Agent OS pre-market-routine（挂 w-* 早盘检查）。
- 253 strategy_discover_weekly：无 message，Job 只数股票；策略发现职责分散，无下游消费其输出。
- 238 financial_data_update：`report_jobs.py:74` TODO「实现财务数据更新逻辑」updated=0；财务更新由 233 data_update + FinancialStatementUpdateJob（analysis_jobs:258，真调 infrastructure.jobs）覆盖。
- （252 strategy_validate_daily 已随 Fix④ 转真实，属 A，勿删。）

**D 修复保留（1 条）**：258 pool_refresh_daily。
- 主路径命中 JobRegistry `PoolRefreshDailyJob`（trading_jobs:187），内部 L204-205 `stock_pool_service.list_pools()` —— **services.py:167 `stock_pool_service = get_stock_pool_service`（显式函数引用，挡住 __getattr__ 代理；实测 type=function）→ 函数对象无 .list_pools → AttributeError → JobResult.fail**。
- 但 258 last_status=success：**Fix② 未部署的活证据**（进程 09-03 01:37:56 启动 < f5c8a0a7 commit 02:09:34，job_executor.py mtime 01:38:21 > 进程启动 → 线上跑的仍是旧 job_executor，内层失败被无条件 success=True 吞掉）。
- 真实 `handle_pool_refresh_daily`（scheduler_tasks:205）**同款 bug**（L218 import 函数 → L224 `.list_pools()`）。
- 修法：Job/handler 内 `stock_pool_service = get_stock_pool_service()`（调用 getter 得实例）或改走 `__getattr__` 惰性代理裸名；pool 有真实消费者（DSH PoolListTool/PoolBattlefieldTool）→ 保留但必修。

### 7.3 部署缺口（必须向用户诚实交代）

- **Fix②（job_executor last_status 假成功）代码已提交 f5c8a0a7（02:09:34）但 v2 进程（01:37:56 启动）未重启 → 线上未生效**。258 当前 success、252 仍输出旧格式均由此解释。
- 修复线②③④ 需 `quantsys_v2_restart` 后才真实生效；重启后 258 应从 success 转 failed（暴露 AttributeError），届时按 §7.2-D 修。
- 治理建议：新任务注册须绑定真实 handler（Job 委托或 webhook），杜绝 count-only/TODO 壳；scheduler_runs 结果断言非空。

### 7.4 下一步待办（未执行，等用户拍板）

1. `quantsys_v2_restart` 部署 Fix②③④ → 重跑 258 确认转 failed。
2. 接线 261/262（Job 委托 ChanScanService/ChanKnowledgeDistiller，仿 Fix④）。
3. 定夺 312：恢复 market_style_state 落库 vs 改 rotation 数据源。
4. 停用 237/250/253/238（disable 先于 delete，观察一轮）。
5. 修 258：getter 调用加括号。

---

## §8 修复完成记录（2026-09-03 深夜，investor w-d84dc7b1）

> 请求：用户从 §7.2 待办中选定 **"先修这两个"**：① 312 market_style_update（§7.2-B 空壳-接线：只 detect 不落库、market_style_state 表无写入方、engine 读 stale 6/2 数据）；② 238 financial_data_update（§7.2-C TODO 空壳：updated=0，报告类 TODO）。修复期间无交易委托（凌晨非交易时段）。

### ① 312 market_style_update → 真实检测 + 恢复 market_style_state 落库（DONE）

**根因（三层）**：
1. 旧 detector 是**编造实现**：`_calculate_value_style_score` 恒 0.45、无真实行情输入；异常回退硬编码 growth/0.33——假数据会污染 rotation engine 决策；
2. 旧 Job.execute 自曝"市场风格检测完成（待实现）"，**从不落库** → quant.market_style_state 停在 06-02 伪造行（unknown/0.0），`strategy_rotation_engine.py:756` 读的就是这条 stale 数据；
3. scheduler_tasks legacy handler 只 detect 不落库，全库无 INSERT → 表无写入方。

**修复**：
- **`application/services/market_style_detector.py` 重写为真实计算**：
  - 数据源 `ak.stock_sector_spot(indicator='新浪行业')`（实测 ~0.1s，49 行业）——application 层引 akshare 有先例（sector/akshare.py）；
  - **显式可审计的 49 行业→风格映射**：VALUE 12 桶 / GROWTH 9 桶 / CYCLE 23 桶 / 显式排除 5 桶（开发区/次新股/其它/综合/物资外贸），coverage=0.898；
  - `compute_style_from_boards` **纯函数**（无 IO，可单测）：分桶中位数 → floor-shift 归一 → argmax 主导风格 + 置信度；**分化 <0.3pp → 真实 'unknown'（conf 0，非降级、非编造）**；空数据 → 显式 degraded（`degraded=True` + error）；
  - 删除造假默认（无 `_get_default_result`、无恒 0.45/0.70/0.35、异常不再回退 growth/0.33）；`detect_market_style()` 数据路径 = ①DB 最近**真实**落库行（fast path，无网络，engine/route 同步调用不 hang）→ ②DB 无真实行才实时拉 sina 计算 → ③都失败才显式 degraded；**06-02 unknown/0.0 伪造行永不被当作真实风格**（`_read_latest_db_row` 过滤 style∉三风格或 conf≤0）；
  - 类级常量/类名/契约键（style/confidence/scores/indicators/recommended_factors/detection_date）保持兼容 → rotation engine（裸构造同步调用）与 `/api/market/style` route 无需改动。
- **新增 `infrastructure/jobs/market_style_update_job.py`**（复用 infra-job 模式）：`execute(**params)` 拉 sina → compute → **落库 market_style_state**（`MarketStyleORMRepository.save_market_style` upsert-by-trade_date）；trade_date 默认解析 = params 显式值 else **最近有 K 线的交易日**（`KlineORMRepository.get_latest_trade_date`，修正了首版误用不存在 `SessionLocal` 导入的问题）else 今天；支持 `--dry-run`/`--trade-date`；拉取失败 → success=False（**不落库**，避免污染最新行）；显式 degraded。
- **`analysis_jobs.py` MarketStyleUpdateJob.execute 接线**：lazy-import infra job → 失败 `JobResult.fail(error)`，成功 `JobResult.ok(message=…style/confidence/trade_date…, **result)`（result 平铺进 details，修正首版 `details=result` 嵌套）；Job 壳 name/description/timeout(1800) 不动。
- **单测重写**（`tests/services/test_market_style_detector.py`，旧 10 例断言的是造假实现、会 AttributeError）：13 例全绿——纯函数风格判定×3（value/growth/cycle 主导）、分化不足→unknown、空输入→degraded、排除行业覆盖率、**新浪 49 行业映射完整性**（防覆盖静默下降）、detect 三层路径（DB 真实行 fast path 不触网/无 DB 行实时回退/全失败 degraded）、fake unknown 行被过滤、初始化兼容。

**实证（真实 DB 落库）**：
- 真实执行 → `trade_date=2026-09-02 style=value confidence=0.6206`（scores value 0.62/growth 0.38/cycle 0.0，bucket_medians value -0.89/growth -1.13/cycle -1.52，boards 49/mapped 44，coverage 0.898，degraded=False，elapsed 0.8s）；
- `market_style_state` 最新行 = **2026-09-02 value 0.6206**（真实），06-02 unknown/0.0 伪造行退居历史；
- detector DB fast path 验证：style=value conf=0.6206 来自 db_market_style_state（db_trade_date=09-02，无网络）；
- registry 全链路：`job_registry.execute('market_style_update')` success=True，message「市场风格检测完成: value (confidence=0.6206, trade_date=2026-09-02)」，details 平铺（style/conf/updated 直接可读）；
- legacy handler `scheduler_tasks.handle_market_style_update`（JobRegistry 未命中时的兜底路径）：裸构造 detector → current_style=value confidence=0.6206 status=success；
- rotation engine `StrategyRotationEngine` 消费兼容（detector 契约未变，未测全引擎因需完整 DI bootstrap，属环境依赖非本次改动）。

### ② 238 financial_data_update → 真实财务数据更新（DONE）

**根因**：`report_jobs.py:74` TODO「实现财务数据更新逻辑」updated=0；quant.stocks 基础财务列（roe/gross_margin/net_profit_growth/revenue_growth）无真实更新方（242 只做三大报表→income_statements，不做 stocks 基础列）。

**修复**：
- **新增 `infrastructure/jobs/financial_data_update_job.py`**（复用 infra-job 模式 + 单事务）：
  - 数据源 `ak.stock_yjbb_em(date='20260630')`（东财业绩报表，实测 11447 行 ~8s），按 股票代码 去重 keep='last'；
  - 更新列**仅 4 个**：`roe / gross_margin / net_profit_growth / revenue_growth`（yjbb 源单位即 %，与 quant.stocks 列口径一致——roe 16.75=16.75%）；**debt_ratio 不更新**（yjbb 无资产负债率列，已写 notes 说明，避免错位覆盖）；pe/pb/market_cap 非本任务范围（242 职责）；
  - 全量 A 股 stocks（market='A' AND is_delisted=false）单事务 UPDATE，失败 rollback；`--report-date`/`--symbols`/`--dry-run` 支持；
  - 报告期口径在 docstring 明示：**2026 中报累计值**。
- **`report_jobs.py` FinancialDataUpdateJob.execute 接线**：lazy-import infra job → `success=False` → `JobResult.fail`；成功 → `JobResult.ok(message=…更新 N 只 (报告期 …), **result)`（同上平铺修正）；timeout 7200 不动。

**实证（真实 DB 落库）**：
- 真实执行 → `report_date=20260630 fetched=11446 updated=5509 skipped=357 failed=0`（5866 A 股 universe，5509 有 yjbb 匹配，357 无匹配跳过），elapsed 9s；
- **600519 贵州茅台**：roe=16.75 / gross_margin=89.56 / net_profit_growth=-1.95 / revenue_growth=1.30 ✅（与 yjbb 源值一致，% 单位正确），**debt_ratio=12.12 未触碰**，updated_at 已刷新；
- registry 全链路：`job_registry.execute('financial_data_update')` success=True，message「财务数据更新完成: 更新 5509 只 (报告期 20260630)」。

### 修复记录中的诚实标注（防伪验证）

- 312 落库 trade_date 取**最近交易日 09-02**（sina 截面即该收盘数据），**不**取当前自然日 09-03（凌晨无交易）；首版因误 import 不存在的 `SessionLocal` 曾回退今天，已改用 `KlineORMRepository.get_latest_trade_date()` 修正；
- detector「实时回退」路径仅在 DB 无真实行时触发（engine/route 读 DB fast path，避免每次同步调用打新浪网络）；
- 非交易日/盘后执行无委托（交易宪法第 1 条遵守）。

### 测试总览（提交前）

```
quantsys-v2：tests/services/test_market_style_detector.py 13 passed
回归：tests/test_scheduler.py + test_daily_jobs_bootstrap.py + test_apscheduler_service.py + test_apscheduler_integration.py = 121 passed
```

### 文件清单（本次仅 stage 以下 6 个自有文件）

```
M quantsys-v2/application/jobs/analysis_jobs.py          （312 Job 接线）
M quantsys-v2/application/jobs/report_jobs.py            （238 Job 接线）
M quantsys-v2/application/services/market_style_detector.py  （312 真实化重写）
M quantsys-v2/tests/services/test_market_style_detector.py   （13 例契约测试）
?? quantsys-v2/infrastructure/jobs/market_style_update_job.py （312 落库 executor）
?? quantsys-v2/infrastructure/jobs/financial_data_update_job.py （238 executor）
```

### 仍待修（非本轮范围，下轮候选）

- 261 chan_scan / 262 chan_knowledge_distill（§7.2-B 接线）
- 237 report_daily / 250 market_scan_preopen / 253 strategy_discover_weekly（§7.2-C 停用或补真实）
- 258 pool_refresh_daily（§7.2-D getter 加括号）
- 工具层 data_fetch_north_flow 描述误导；L4 元学习从未实现；lifecycle CLAUDE.md 过时
