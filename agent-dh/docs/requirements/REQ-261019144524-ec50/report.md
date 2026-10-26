# 进化闭环有效性调研报告

- **需求**：REQ-261019144524-ec50《进化闭环有效性改造：让自我进化以盈利为北极星》（spike）
- **汇总**：t-c5c85c · 2026-10-19 · w-503df447（investor）
- **触发**：用户原话「自我进化，感觉没有用，没有提高投资的准确性和发现盈利机会」
- **一句话结论**：用户负反馈实证成立。进化闭环在结果层零产出、内容层零交易进化、运行层假运转；根因不是某一个 bug，而是「北极星错位 + 样本断流 + 输入污染 + 失败无告警」四环互相喂毒。本 spike 已交付：北极星 KPI 与周报度量（已上线）、观察计分 SOP（已落地）、策略库/经验库治理清单（待裁决）、小仓位试单授权建议书（待批准）、触发链失败的真实根因定位（口径已修正）。

---

## 1. 四线结论与证据链接

### 1.1 投资结果层：进化没有可衡量的产出 ✅ 证实

| 证据 | 数据 | 来源与时点 |
|---|---|---|
| 账户几乎不交易 | 总资产 49.9 万、现金 96.9%、持仓 2 只（002007/600000，市值 1.54 万）、总盈亏 -0.97% | position_list(account_name=<本实例投资账户>)，2026-10-19 实调 |
| 自有决策评分 = 0 | decision_scores 27 条 100% 为策略线账户 v13/v14 回填（逐条核对 context.account），本实例账户覆盖 **0 条**；全量 20 日平均超额 -10.24%、18/27 big_loss | decision_scores，2026-10-19 实调 |
| 经验库以噪声为主 | 库内真值 343 条（工具 200 条截断口径已修正），真实标的经验仅 **73 条（21.3%）**；270 条非标的（78.7%） | psql 全量五分桶，2026-10-19，见 [w4-experience-cleanup.md](w4-experience-cleanup.md) §1 |

### 1.2 进化内容层：进化方向与盈利脱钩 ✅ 证实

- genome_history g22~g40 全为工程纪律（R-015~R-021、部署/观测/schema 类 lessons），**无一条交易层进化**（2026-10-19）。
- 结构性死锁成立：R-016 样本门槛 ≥7 → 账户零交易样本=0 → 只能改工程规则 → 不产生交易 → 样本继续=0。破局件已备好：观察计分 SOP（W3，零风险先行）+ 小仓位试单授权建议书（W3-授权级，[RFC 017](../../rfcs/017-small-position-trial-authorization.md)，待用户批准）。

### 1.3 信号源层：无米之炊 ✅ 证实（形态修正）

- 策略主表 TEST 残留**已清零**（09-13 清 320 条）；当前仅 5 条 user 策略且 **5/5 全 unmeasured（0%）**。真正残留在派生表：backtest_results 540 行孤儿 + evolution 两表 106 行悬空，均无 data_contracts 登记（R-020 盲区）。见 [w4-strategy-cleanup.md](w4-strategy-cleanup.md)。
- 补测阻塞于两个实测缺陷：①evolution_run 降级被工具 schema 拦成硬错误（连续第 4 周复现）；②「零交易」判据缺陷（实际 -23.18% 有交易的回测被判无信号），补测判据须禁用 totalTrades。

### 1.4 机制运行层：假运转 ✅ 证实（根因口径修正）

- **设计阶段根因被证伪**：「webhook 任务被按占位 command 执行」是 2026-09-03 的历史数据缺陷（09-15 已修 17 行任务数据）；executor.go L109 webhook 优先分支本身无 bug。见 [w1-trigger-diagnosis.md](w1-trigger-diagnosis.md)。
- **真实根因**：2026-10-14~10-19 DSH（13080）停机 → 30+ 条任务失败全部 `connection refused`；59 条补投耗尽上限**永久丢失且无任何告警**。10-19 午后 DSH 恢复后 webhook 任务全部 ✅（scheduler_manage list 实调），证明触发链断在「对端存活」而非「通道选择」。

## 2. 根因假设逐条裁决（需求 §3）

| # | 假设 | 裁决 | 关键证据 |
|---|---|---|---|
| 1 | 北极星错位 | **证实** | g22~g40 无交易层进化；已立 W2 三 KPI + 周报强制段 + 连续 4 周无改善降频规则（[w2-northstar-kpi.md](w2-northstar-kpi.md)） |
| 2 | 反馈环断裂于源头 | **证实** | 本账户决策评分 0 条；破局=观察计分先行（[w3-observe-scoring-sop.md](w3-observe-scoring-sop.md)）+ 授权试单后置（RFC 017） |
| 3 | 输入质量不治理 | **证实，形态修正** | TEST 残留不在主表在派生表；经验库 78.7% 非标的；两份治理清单已出、处置待用户裁决 |
| 4 | 失败无告警闭环 | **证实且加强** | DSH 停机 5 天无告警；59 条补投永久丢失无告警；策略库 14→101→5 两次变动无台账；reqboard FINALIZE_PARENT 失败连续 3 次无人消费（w1 §7） |

## 3. P1-P4 验收指标逐条实测（design §5 对照）

| 阶段 | 验收指标 | 实测值（2026-10-19） | 判定 | 复核命令 |
|---|---|---|---|---|
| **P1 修触发** | 进化类 Agent 任务成功率 ~20% → **≥90%** | 口径已修正：失败根因=DSH 停机（connection refused），非通道 bug。10-18 周末批次全 ❌、10-19 上午 ❌（DSH 未起）、10-19 午后恢复后 webhook 任务全 ✅。**成功率目标未达成**——修复对象（DSH 存活保障 + 多天停机告警闭环）属后续实施卡，本 spike 只完成诊断与口径修正 | ⚠️ 部分（诊断✅ 指标❌） | `scheduler_manage(action=list)` 看"上次结果"列；`agent_os_logs(source=scheduler, grep="connection refused")` |
| **P2 立度量** | 周报含三项北极星指标数值；数据源可复核 | ✅ 已上线：weekly-report-m6（afe560bc）payload 已改写含三 KPI 强制段+降频规则（update 后 get 复核一致）；KPI 口径与基线落 w2。首次含 KPI 周报产出时点 = 2026-10-25（周日 12:00） | ✅ 达成（机制侧） | `scheduler_manage(action=get, task_id=afe560bc-dc9b-4692-982f-1cd1a10e85d6)` 看 payload；KPI 取数：`signal_track(report)` / `decision_scores` / `experience_stats` / `strategy_list` |
| **P3 通样本** | 本账户自有决策评分样本 0 → **≥7** | 观察计分 SOP 已落地（w3），C 级落库机制实证已闭环（82 信号中 C 级 53 条，有回填胜率）；但本账户决策评分样本仍为 **0**（decision_scores 逐条核对，27 条全策略线回填）——≥7 需样本积累期（信号 20 交易日回填周期）或授权试单（RFC 017 待批） | ⚠️ 部分（机制✅ 样本❌） | `decision_scores` 明细逐条看 `context.account`；`signal_track(action=report)` |
| **P4 清输入** | 策略库 TEST-* 清零；measured 占比 ≥50%；经验库 unknown-symbol <30% | TEST-* 主表 **0 条 ✅**（09-13 已清）；measured 占比 **0/5 = 0% ❌**（阻塞于 trades 计数缺陷 + evolution_run schema 缺陷，补测序见 w4 §4）；经验库非标占比 **78.7%（270/343）❌**（处置方案已出，保留 73/隔离 85/作废 185，执行待用户裁决） | ⚠️ 部分（清单✅ 指标❌） | `strategy_list`（5 条全 unmeasured）；`psql quant_investment -c "SELECT count(*) FROM memories WHERE category='experience'"`（343）对照 w4-experience §1 分桶 SQL |

**诚实声明**：P1/P3/P4 的数值型指标本 spike 未达成——spike 的交付边界是「诊断 + 度量 + 清单 + 建议书」（design §1 范围），数值改善依赖后续实施卡与用户裁决。若验收要求四项数值全绿，则本需求应判「部分通过」并把未达项转后续需求；本报告建议按 spike 交付物口径验收（§4）。

## 4. Spike 交付物清单（对照需求 §6）

| # | 交付物 | 状态 | 位置 |
|---|---|---|---|
| 1 | 调研报告（本文）：证据链复核 + 根因假设逐条裁决 + 失败原因排查结论 | ✅ | 本文件 |
| 2 | 推荐方案 A/B/C/D 取舍与分阶段路径、可证伪验收指标 | ✅ | §3 实测对照 + §5 |
| 3 | 方向 B 授权边界建议（仓位上限/信号级别/止损纪律） | ✅ | [w3-trial-budget-proposal.md](w3-trial-budget-proposal.md) + [RFC 017](../../rfcs/017-small-position-trial-authorization.md)，待用户 A/B/C 三档裁决 |
| 4 | 工作包产出：W1 诊断 / W2 KPI / W3 SOP / W4 策略库清单 / W4 经验库清单 | ✅ | w1-trigger-diagnosis.md / w2-northstar-kpi.md / w3-observe-scoring-sop.md / w4-strategy-cleanup.md / w4-experience-cleanup.md |

## 5. 推荐方案与后续路径（A/B/C/D 组合取舍）

**取舍**：D（失败闭环）与 A（重定义 KPI）已落地机制侧；C（输入治理）清单已出待裁决；B（主动造样本）拆为「观察计分先行（已落地，零风险）+ 授权试单后置（RFC 017 待批）」。

**建议后续实施卡（均需另立项，不在本 spike 边界）**：
1. **DSH 存活保障与停机告警**（P1 真正的修复对象）：多天停机超补投窗口时飞书高优告警；17 条占位 command 清空防御；scheduler UpdateTask 对 command/webhook_url 变化触发重排（scheduler.go L167）。
2. **补测前置修复**：回测 trades 计数缺陷（窗口末强制平仓或改判据）+ evolution_run 降级 schema 分支；然后对 163/178/179/193 跑 1 年 OOS 补测，把 measured 占比从 0% 拉起。
3. **经验库处置执行**（待用户对 w4-experience §3 三档方案拍板后执行，先备份 + R-020 登记）。
4. **reqboard 观测面**：FINALIZE_PARENT 失败/子卡速通无产出（本需求实证 2 例：t-9bae04 三子卡 17 秒速通零产出）纳入看门狗告警。
5. **RFC 017 用户裁决**：A/B/C 三档；批准则以月度熔断 2,500 元为界开始积累自有样本，P3 的 ≥7 目标才有达成路径。

## 6. 边界遵守声明

- 未修改任何 R-xxx 交易规则/仓位档位/止损线（R-016 与本需求边界）；
- 未在 agent_brain 开任何新仓（position_list 复核：002007/600000 两只无变化）；
- 未删除任何策略/经验记录（两份清单全部处置动作列为待用户裁决）；
- 唯一写操作：weekly-report-m6 任务 payload 改写（W2 验收项）+ 测试信号 record ID 166（w3 验收项，reason 已标注【SOP验收测试信号】）。
