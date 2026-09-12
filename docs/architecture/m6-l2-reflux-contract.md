# M6 ↔ L2 决策回流契约（Reflux Contract）

| 字段 | 值 |
|---|---|
| 状态 | ✅ 生效中（2026-09-12 起） |
| 创建 | 2026-09-12（w-c8cae280） |
| 需求 | REQ-9bcd0a |
| 上游 | [autonomy-profit-engine-unified.md](./autonomy-profit-engine-unified.md)（两线定义与唯一接口=genome） |

---

## 1. 为什么需要这份契约

两线文档定义了**唯一接口 = genome**（引擎读规则、Autonomy 改写规则），但**没有定义反方向的边**：
「引擎/L2 的产出（评分/归因/教训）→ 怎么变成消费方的输入、谁负责、多久内、缺失怎么办」。

后果（2026-09-12 实测）：评分器已生产运行并量化出「16 笔买入决策 20 日平均超额 **-10.24%**、**18/27 big_loss**」，
归因每天 18:40 准时写入记忆库 —— 而**同一个系统在 09-12 问「还缺什么」时，既没引用归因，也没读评分**。
**产出无人消费等于没有产出。** 本契约把这条边从"默认存在"变成"有定义、有负责方、可判红绿"。

## 2. 契约要素定义

每条回流契约必须写清 7 项：**产出方 / 数据形态 / 存放位置 / 消费方 / 时限 / 缺失语义 / 可观测性**。

## 3. 现行三条契约

### RC-1 业绩归因（引擎线 M6 → 全部分析场景）

| 项 | 内容 |
|---|---|
| 产出方 | 定时任务 `attribution-daily`（工作日 18:40，task `cea8af50…`） |
| 数据 | 组合窗口收益 / 基准 / 超额 / beta / alpha / IR / navPoints；不可归因时须显式写"无法归因"并给出根因，**禁止用 0 冒充**（R-013） |
| 存放 | `memory_write(namespace=analysis)`，key 短语含「业绩归因」 |
| 消费方 | 盘前例程（9:25 第⑧步）、盘后复盘、任何"要不要开仓"的分析 |
| 时限 | **次日盘前** |
| 缺失语义 | 消费方必须在 `decision_audit(record)` 的 context 写 `attribution_read=false` **并说明原因**；禁止静默跳过 |
| 可观测性 | 智能执行页检查点 `m6_attribution`（产出侧，18:40） |

### RC-2 决策评分与教训（Autonomy L2 → 决策前必读）

| 项 | 内容 |
|---|---|
| 产出方 | `DecisionScoreService`（`daily_orchestrator._phase_review` 调度；满 20 交易日打分） |
| 数据 | `score` / `band` / `excess_return` + **`learned_lesson`**（教训，2026-09-12 起由 `lesson_generator.generate_lesson` 产出） |
| 存放 | `agent_decisions` 表；只读出口 `GET /api/evolution/decision-scores` |
| 消费方 | `decision_scores` 工具（agent-dh，2026-09-12 上线）/ 盘前例程第⑧步 |
| 时限 | 决策前 |
| 缺失语义 | `summary.lessonCoverage.rate = 0` 即**回流边断链**（评分有、教训无），必须上报而非忽略 |
| 可观测性 | 同上 `m6_attribution` + `decision_scores` 工具的 `lessonCoverage` |

### RC-3 消费纪律（规则层，R-008 扩展）

| 项 | 内容 |
|---|---|
| 载体 | genome `rules` 段 R-008（2026-09-12 扩展，rules v16 / genome g28，候选 `cand_1789220789501_2mah72`，观察至 2026-09-17） |
| 内容 | 分析/复盘前必须读 ①昨日业绩归因 ②决策评分与教训，并在 `decision_audit` context 写明 `attribution_read` 与引用数值；取不到显式记 false |
| 可观测性 | 智能执行页检查点 **`m6_l2_reflux`**（消费侧，09:25，判定语义：`attribution_read=true` → 绿；`false` → **红（回流边断链）**；今日无盘前分析记录且过宽限 → late；未到点 → pending） |

## 4. 责任划分

| 环节 | 负责 | 说明 |
|---|---|---|
| RC-1 产出 | 引擎线（M6，qv2 定时任务） | 归因归入 M6 学习飞轮 |
| RC-2 产出 | Autonomy L2（qv2 `application/services/evolution/`） | 评分与教训是"分析评估"产物 |
| RC-1/RC-2 消费 | 引擎线（agent-dh 工具面 + 盘前/盘后例程） | 工具化 + 强制步骤 |
| RC-3 规则 | Autonomy L3（genome candidate → validation_gate） | 不得直接改 active |
| 契约维护 | 本文件；两线交界变更须同步更新 | 交界变更是"两条线都以为自己不用做"的高风险区 |

## 5. 已知缺陷与风险（必须跟踪）

1. **G1/C2 登记缺失（未修）**：`genome_update(stage=candidate)` 不写 `candidates.json` → 候选不进观察流水线、**永远不会被 validation_gate 裁决**（空转孤儿）。2026-09-06 审计首次发现，2026-09-12 再次复现（本次已人工补录 + 备份）。**任何走该路径的变更都会重蹈此辙**，需修 `registerCandidate` 接线。
2. **前向路径时效**：评分服务需重载代码后新打分轮次才产教训；回填类操作不受影响。
3. **基准新鲜度**：基准（沪深300）滞后时归因结论不可用，此时须显式"无法归因"，不得降级为 0。

## 6. 验收判据（可执行）

| 判据 | 命令/证据 |
|---|---|
| S1 工具可达 | 调用 `decision_scores` 返回 total≈27 与 band 分布（无需 curl） |
| S2 教训非空且可区分 | `lessonCoverage.rate` > 0，且每条含 标的+日期区间+超额+band |
| S3 归因被真正消费 | 盘前例程当日 `decision_audit` context 含 `attribution_read` 与引用数值 |
| S4 断链可见 | 智能执行页 `m6_l2_reflux` 在未读归因时显示红（failed） |
