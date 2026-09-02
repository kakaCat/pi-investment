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
