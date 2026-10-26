# W2 北极星 KPI 定义与周报度量口径

- **需求**：REQ-261019144524-ec50 进化闭环有效性改造（SP-2 / 工作包 W2）
- **任务**：t-954eb4（研发子卡 t-d176e2）
- **落盘**：2026-10-19 · 实施窗口 82bffa4a-f359-45d5-ae50-ffadfccb4398
- **依据**：[design/design.md](design/design.md) §2 W2 / §3 目标架构 / §5 P2 验收指标（周报含三项北极星指标数值；数据源可复核）

## 0. 一句话定义

进化的有效性用投资结果度量。周报必须强制回答：**本周进化让三项北极星 KPI 变了多少？**
连续 4 周无改善 → 进化类任务自动降频（见 §4）。

## 1. KPI-1 信号胜率（Signal Win Rate）

| 项 | 口径 |
|---|---|
| 定义 | 本周新落信号在 5/10/20 交易日的命中率与平均收益，按 A/B/C 分级（R-009）拆分 |
| 数据源工具 | `signal_track(action=report, start_date=周一, end_date=周日)` |
| 关键字段 | `details.byGrade.{A,B,C}.{count, hitRate5D, avgReturn5D, hitRate10D, avgReturn10D, hitRate20D, avgReturn20D}`、`details.bySource` |
| 主指标 | **B 级及以上（A+B）10 日胜率**（5 日噪声大、20 日回填滞后；A 级样本常年过少，单列但不作主判据） |
| 实测基线 | 2026-09-19~2026-10-19：82 信号（A3/B26/C53）；5 日胜率 A 33.3% / B 30.0% / C 26.5%；10 日胜率 A 100%（n=3，样本不足不作结论）/ B 44.4% / C 33.3%（signal_track report，2026-10-19 实调） |
| 注意 | hitRate20D 回填滞后约一个月，近 4 周窗口常为 null——null 不等于 0，引用时必须标注"未回填" |

## 2. KPI-2 决策超额（Decision Excess Return）

| 项 | 口径 |
|---|---|
| 定义 | 已完成 20 交易日评分的决策相对基准（sh000300）的超额收益分布与均值 |
| 数据源工具 | `decision_scores`（汇总永远基于全量，明细须逐条看 `items[].context.account` 过滤本实例账户） |
| 关键字段 | `summary.{meanExcessPct, byBand.big_loss/big_win, lessonCoverage.rate}`、明细 `excessReturnPct` / `band` / `context.account` |
| 主指标 | **本实例账户（agent:identity 段账户名）的 meanExcessPct 与 big_loss 占比** |
| 实测基线 | 27 条已评分决策 100% 来自策略线账户回填（v13_simulation/v14_simulation）与 missed_opportunity（无账户），**本实例账户覆盖 0 条**（decision_scores 实调，2026-10-19）。全量均值 -10.24%、18/27 big_loss 是策略线成绩，**不得当作本实例业绩先验**（R-018/R-019） |
| 注意 | 工具本身无 account 过滤参数——必须取明细逐条核对 `context.account`；覆盖为 0 时周报如实写"本账户无自有样本"，禁止拿全量均值冒充 |

## 3. KPI-3 机制健康度（Mechanism Health，三个子项取弱项）

| 子项 | 定义 | 数据源工具 | 实测基线（2026-10-19） |
|---|---|---|---|
| 3a 进化任务成功率 | autonomy 线进化类 Agent 任务（evolution-distill-daily / evolution-gate-adjudicate / evolution-weekly-variant / meta-learning-weekly / agent-brain-weekly-evolution / agent-brain-weekly-distill / data-hygiene-weekly 等）最近一周运行 success 占比 | `scheduler_manage(action=list)` 读"上次结果"列 | 2026-10-18 批次大面积 ❌ failed（周报任务自身亦 failed），成功率 <20% |
| 3b 经验库有结局占比 | experience 命名空间中 outcome ∈ {profit, loss, neutral} 的记录占比（untagged = 无结局） | `experience_stats` 读 `by_outcome` | (3 profit + 15 loss + 43 neutral) / 200 = **30.5%**，untagged 139 条（其中 unknown-symbol 154 条属 t6 治理范围） |
| 3c 策略库 measured 占比 | performanceStatus ≠ unmeasured 的策略占比（passing/underperform/failing 都算已度量） | `strategy_list`（全量；后端 `GET /api/strategies` 可复核） | **0/5 = 0%**（全 unmeasured；策略库 125→5 已经 t5 线清理，TEST 残留已不在库） |

**合成规则**：三项子指标任一恶化即整体判"不健康"；周报逐项报数值，不做加权平均（避免好项掩盖坏项）。

## 4. 降频规则（连续 4 周无改善 → 进化任务降频）

- **判定**：连续 4 期周报中，三项 KPI 全部满足"无改善"——
  - KPI-1：A+B 级 10 日胜率周环比不升（含样本为 0 的周）；
  - KPI-2：本账户无新增自有评分样本，或已有样本 meanExcessPct 不升；
  - KPI-3：三个子项均不升。
- **动作**（周报任务在当期周报中执行，落 decision_audit + memory 留痕）：
  1. `scheduler_manage(update, enabled=false)` 暂停：evolution-weekly-variant、meta-learning-weekly；
  2. `evolution-distill-daily` 由工作日每日降为每周一次（改 cron 为 `0 0 23 * * 1`）；
  3. 保留不动：weekly-report-m6 自身、evolution-gate-adjudicate（验证门裁决不能停，否则 candidate 永不转正）、weekly-report-m6 的 KPI 采集段。
  4. 飞书告警（alerts, high）：降频触发事实 + 近 4 周 KPI 数值序列。
- **恢复条件**：任一 KPI 出现可验证改善，或用户明确指示恢复；恢复同样走 scheduler_manage 并留痕。
- **纪律**：降频只动调度频率，不改任何 R-xxx 交易规则/仓位档位（本需求不触碰交易规则，design §1）。

## 5. 周报模板改造（已落到 weekly-report-m6 payload，2026-10-19）

任务 ID `afe560bc-dc9b-4692-982f-1cd1a10e85d6`（周日 12:00，agent-webhook）。在原"调用 weekly_report 生成并推送"基础上新增**强制段落**：

1. 【北极星 KPI 速览】三段式逐项给数值 + 周环比箭头（↑/→/↓）+ 数据源工具名与时点（R-013）；
2. 【KPI-2 账户过滤】decision_scores 必须逐条核对 context.account，写明本账户覆盖样本数；为 0 如实写；
3. 【降频判定】对照 §4 给出"本周是否累计触发连续无改善"的判定与计数（n/4）；
4. 【可复核性】每项数值后标注取数命令（工具+参数）， reviewer 可原样复跑。

## 6. 验收锚点（本卡 dev 段）

- [x] 三项指标数据源工具与口径确定并实测取到数值（§1/§2/§3 基线列，全部 2026-10-19 实调）
- [x] KPI 定义文档落盘（本文件）
- [x] weekly-report-m6 payload 经 scheduler_manage update 改写，含三项指标采集指令与 §4 降频规则（update 后 get 复核全文一致）
