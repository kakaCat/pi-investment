---
name: engine-heal-evolve
description: 盈利引擎（genome+learning 决策系统）自进化流水线 SOP：诊断决策质量缺口 → 归因分层（选股/择时/执行/规则/数据）→ 分诊到对应修补通道 → 单主题 genome_update(candidate) → validation_gate 验证转正 → R-010 汇报。回答"决策怎么变强/规则改进/复盘进化"类问题或收到 OS 定时进化任务唤醒时按此执行，禁止无证据硬改规则。
whenToUse: 收到 OS 定时任务唤醒（evolution-weekly-variant / evolution-gate-adjudicate / evolution-distill-daily / meta-learning-weekly / weekly-report-m6）、用户问"怎么让决策变强 / 复盘进化 / 规则改进 / 最近亏在哪"，或盘后复盘发现重复错误模式需沉淀规则时
---

# 盈利引擎进化流水线（Engine Heal & Evolve）

> 定位：这是**决策系统自进化**的操作手册（skill），与 genome 分工——genome 存常驻短约束（rules/lessons/principles），本技能存"诊断→修补→验证"的完整流程。**盈利引擎 = 每次决策后证据留痕 → 定期诊断缺口 → 单主题修补 → 观察验证 → 转正/回滚**，让"我"的决策规则持续变强。
> 铁律：交易宪法（constitution 段）禁止改动；交易时段（9:30-11:30、13:00-15:00 A股交易日）不做非紧急规则大改；**每一步必须真实调用工具取证，禁止凭记忆/感觉修补**。

## 第 0 步：身份核验与场景识别（R-011 精神：先核验再执行）

被唤醒/被问到时先回答三问，不急着动手：

1. **这是什么场景**？看消息来源与任务名：
   - `evolution-weekly-variant`（周六 10:00）→ 变异：prompt_evolver 挑建议做 candidate 应用
   - `evolution-distill-daily`（工作日 23:00）→ 蒸馏：experience 沉淀
   - `evolution-gate-adjudicate`（周日 11:00）→ 裁决：validation_gate 裁 candidate
   - `meta-learning-weekly`（周日 11:30）→ 元学习分析
   - `weekly-report-m6`（周日 12:00）→ 周报
   - 用户直接问 → ad-hoc 诊断
2. **要操作的对象健康吗**？凡涉及策略信号源：先 `strategy_list` 核验 status/validationStatus（R-011 教训：VBottom-v2 在 error+invalid 下产出全 SELL 异常批量、字段缺失、理由模板化 → 其输出不可信，默认跳过执行）。凡要裁决的 candidate：先 `genome_benchmark` 结构复核。
3. **有真实证据缺口吗**？无数据支撑的"感觉有问题"不是修补理由；先走第 1 步取证。

## 第 1 步：收集证据（诊断——只读取证，真实调用）

按场景选用以下工具，**至少 2 个维度**交叉才下结论：

- `decision_history`(action=pending, days≥7)：逾期未评估的决策 → 决策质量盲区
- `decision_history`(action=report, entity_type=stock/account)：按实体聚合，找"哪些标的总亏"
- `experience_stats`：经验库总胜率/按标的分布/平均盈亏 → 稳定亏损源
- `learning_analyze`(focus=failures 或 patterns)：识别失败模式
- `genome_history`：各段版本谱系（谁改过、为何、有无 candidate 滞留 watching 过期）
- `signal_track`(action=report)：信号源胜率 → 哪些来源/分级信号质量差
- 涉及仓位/止损类规则时加 `m4_circuit_breaker_check`、`regime_position_limit`、`trade_verify`
- 数据质量问题（怀疑不是规则问题而是数据问题）→ `data_quality_report`、`data_manager`(status)

**输出**：一句话"质量缺口假设"（哪层、什么证据、影响多大）+ 证据清单（工具名 + 关键数字）。假设立不住就回到零操作（第 7 步），不硬凑。

## 第 2 步：归因分层（缺口属于哪一层——最关键的判断）

- **选股层**：标的选错（experience_stats 单标的连亏、signal 胜率 <40%、选入即跌）→ 信号/筛选/股票池问题
- **择时层**：买卖点错（频繁触发止损、止损后反弹、追高被套）→ 规则阈值/时机问题
- **执行层**：规则对但没执行（漏单、犹豫、工具循环、违反 T+1/仓位上限）→ 纪律/流程问题，不是新规则问题
- **规则层**：规则缺失/过时/互相矛盾/与实证冲突 → genome 修补（第 4 步）
- **数据层**：决策所依数据缺失/延迟/错误（K线空、指标 NaN、字段错位）→ `data_manager` 修复，**不是规则问题，禁止用改规则掩盖数据问题**

判据：证据指向哪层就修哪层。**把执行层/数据层问题错写成新规则 = 最典型的引擎空转**。

## 第 3 步：分诊决策树（缺口 → 修补通道）

| 缺口 | 通道 | 说明 |
|---|---|---|
| 规则缺约束/过时/矛盾 | `genome_update`(section=rules, **stage=candidate**) | 最常用；单主题 |
| 单案例教训（防再犯） | `experience_write`(outcome 如实) | 轻量，不进 genome |
| 跨案例稳定规律 | `genome_update`(section=lessons) | 有样本支撑才升级 |
| 原则/流程性过时 | `genome_update`(principles) 或修订本技能 | 流程问题改 SKILL.md 本体 |
| quantsys 策略参数（均线/阈值等） | `evolution_run`(strategy_id, symbol) → leaderboard | **≠ genome**，走策略进化引擎 |
| 某信号源持续差 | `signal_track` 报告 + 降权/停用该源 | 先核验健康（R-011）再处置 |
| 批量高置信建议落地 | `daily_distill` / `prompt_evolver`(suggestions, dry_run→candidate) | 编排通道 |
| 无高置信缺口 | **零操作**（第 7 步） | 宪法第 6 条：不强求进化 |

## 第 4 步：修补执行（单主题铁律）

1. **一次只改一个主题**（可归因）——禁止把"市场不好+选股差+止损松"打包成一次大改。
2. **constitution 段禁止改动**（宪法层锁定）。
3. 修补前 `memory_search`(namespace=experience, query=该场景) 检索历史教训（R-008），reason 注明检索结论。
4. 新规则内容须通过 genome 校验（花括号变量、段大小、规则 ID 不重复）——`genome_update` 自带校验，force 保持 false。
5. 用 **stage=candidate 观察版**（非直接 active），observe_days 默认 5；reason 写：规则 ID + 证据（引决策/经验 ID 或工具数字）+ 预期效果。
6. 规则编号递增不重号（R-xxx 顺序）；教训/原则改动同样走 candidate 观察。
7. 重大修补后 `decision_audit`(record, decision_type=genome_update) 留痕决策链。

## 第 5 步：验证与转正（候选生命周期）

- candidate 到期（observe_days 满）→ `validation_gate`（min_samples≥3，样本不足自动延期 2 天）。
- 结构复核不过（花括号/超限/ID 重复/空更新）→ `genome_benchmark` 防御性置 rejected，按建议 `genome_rollback`（历史只增不改）。
- 裁决通过 → `genome_promote`(section, reason)；失败 → `genome_rollback`。
- 用 `genome_history` 确认版本号变化与谱系（candidate 未转正前不要当作已生效规则引用）。
- 缝隙容忍：gate 只在周日 fire，观察期周中到期的候选会多等几天——**属正常，不补任务**；紧急候选可在到期日手动 `validation_gate(force=true)`。

## 第 6 步：汇报（R-010 任务完成通知）

- 完成修补：`feishu_notify`(channel=reports, urgency=normal)：改了哪段、版本号、观察期到期日、证据摘要、下一步。
- 异常（裁决失败/结构不过/回滚/数据层根因）：urgency=high → alerts 群。
- **零操作也是结果**：normal 简报说明"无高置信缺口，证据不足不硬改"，不留遗憾也不打扰。

## 第 7 步：自检清单（交付前逐项过）

- [ ] 单主题、可归因（第 4 步第 1 条）
- [ ] constitution 未动
- [ ] 证据全部来自真实工具调用（无臆造数据/价格/胜率）
- [ ] stage=candidate + 观察期已安排（非紧急直改 active）
- [ ] memory_search 已检索历史教训并在 reason 注明
- [ ] 决策已 decision_audit 留痕
- [ ] 汇报已发（含零操作简报）
- [ ] 未把 quantsys 策略参数问题当 genome 规则问题（走了 evolution_run）
- [ ] 未把数据层问题写成新规则

## 禁止清单（实证教训固化）

- ❌ 无证据修补（幻觉归因）——规则必须挂证据，宁缺毋滥
- ❌ 一次改多主题（无法归因 = 无法验证 = 引擎空转）
- ❌ 改 constitution 段
- ❌ 把策略参数问题塞进 genome（正路是 evolution_run）
- ❌ 用新规则掩盖数据层故障（先修数据）
- ❌ 在信号源 error+invalid 时逐条核查其批量信号（R-011：先核验健康，异常批量默认跳过）
- ❌ 非紧急规则大改放在交易时段（会留痕 force，干扰交易决策）
