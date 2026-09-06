# Autonomy 线（L1-L4）代码级完成度审计报告

- 日期：2026-09-06（周日）
- 审计人：investor 角色，窗口 w-a8a89c6a
- 触发：用户要求"审计自主能力体系（Autonomy 线）现在的完成进度，主要看代码别假实现"
- 审计对象：agent-dh Autonomy 9 包（lifecycle/learning/evolution/evolver/genome/memory/notification/scheduler）+ 调度链路实证
- 审计方法：**代码逐段读 + 线上状态文件实读 + 调度运行记录（task_runs/memory/genome history）三路交叉**；分级口径：
  - ✅ 真：代码真实 + 行为证据（运行记录/产物/数据落库）佐证
  - ⚠️ 真但断/半通：代码真实但轨未对齐或空转（有实证）
  - ❌ 空洞/占位：声称实现但代码是壳或与后端能力不符
  - 历史假实现（已修复）单独列账，与现存缺口区分

## 一、完成度总览（按证据分级）

| 层/组件 | 分级 | 代码证据 | 行为证据 |
|---|---|---|---|
| **L1 记忆** memory_search/write + experience_* | ✅ 真 | packages/memory 工具经 aos.memory 客户端 → Agent OS /api/v1/memory（2026-08-25 迁移注释） | 9/5 全天 12+ 条记忆实时落库（psql memories 实证）；本审计即靠记忆回溯执行痕迹 |
| **L2 学习** learning_track | ✅ 真 | setupInterceptors@173 挂 waterfall tools/post-execute，isTrackedTool=[portfolio_trade,strategy_execute,model_predict,opportunity_scan,rotation_execute]（2026-08-20 修"监听不存在事件"假实现） | 蒸馏/追踪链路产出 46 样本（9/5 daily_distill 预览） |
| **L2** learning_distill | ✅ 真 | 蒸馏即落库 kind='rule'/status='testing' envelope（2026-09-03 Fix③） | 与 9/3 审计一致 |
| **L2** learning_apply | ✅ 真 | applyRule@537 状态机 testing→active，searchMemory 精确匹配 + PATCH 回读校验 status==='active' 才 applied:true，失败抛错（2026-09-03 Fix③ 重写假占位） | — |
| **L2** learning_analyze/experience_stats | ✅ 真 | 读经验库统计 | 9/5 蒸馏预览产出 |
| **L3 基因组** genome store | ✅ 真 | store.ts：tmpPath 原子写 + git add/commit 留痕 + CHANGELOG | genome history g1→g20 全留痕（含 git_commit），9/5 两次真实更新（g19 candidate R-011 / g20 active R-012） |
| **L3** prompt_evolver | ✅ 真（9/3 修复后） | PromptEvolverTool：LLM 改写 → registerCandidate(candidates.json) + genome_update(stage=candidate) **双写**（RFC 008 修复注释） | g14 转正（8/25）唯一一次完整闭环 |
| **L3** evolution（策略进化） | ✅ 真（9/5 修复后） | 数据源 9/5 切 quantsys-v2：v2 evolution_engine_async.py POST /api/evolution/engine/run 真实回测；strategy_evolution_service.py 头注释"绝不产出占位 fitness"，degraded 诚实降级 | evolution_strategy_runs 87 行 9/5 03:41 仍跑；9/5 14:21 修复完成经双窗口认领复核 |
| **L4** validation_gate | ✅ 真（工具本体） | ValidationGateTool：读 candidates.json + searchRewards 打标经验对比（q=`genome:${version}` kind='experience'）+ L4-B 结构防御 + min_samples=3 延期 | 9/5 19:32 真实执行（memory 86474aef），正确裁决 g19 观察期未满延期（见 E-4） |
| **L4** genome_benchmark（L4-B） | ✅ 真 | 2026-09-03 aa1213c4 结构复核腿 | — |
| **工程** lifecycle 自修复 | ✅ 真 | scheduleFinalize@972 mergeFfOnly/rollback 真实 git 操作；2026-09-04 修 checkpoint 丢失 bug | agent-self wip 45→1 条清理记录（9/5 19:02）证明 merge 链真实运转过 |
| **工程** 调度链路（9/4 迁移后） | ✅ 真（9/5 实证） | lifecycle agent-os-trigger.ts：Agent OS cron → webhook POST 13080/agent-os-trigger → 唤醒 agent（executor mode=direct session 注入） | task_runs：9/5 10:00 variant scheduler success → 10:02 genome g19 产出（端到端 2 分钟）；9/5 19:32 gate delivered memory（executor mode=direct + session id） |
| **工程** NativeReminderScheduler | ⚠️ 空转无害 | native-scheduler.ts filter payload.executor==='dsh-native'；9/4 迁移后 enabled 任务 **0 个 dsh-native**（10 webhook + 7 空） | native-scheduler.json lastFired 停 9/4 13:00（迁移时刻）——职责移交 webhook 轨，无 dsh-native 任务=纯空转不投递 |

## 二、假实现核查结论

### 历史假实现（已修复，非现存——注释/提交实证）

| 假实现 | 修复 | 证据 |
|---|---|---|
| learning_apply "假 applied:true 占位" | 2026-09-03 Fix③ 重写状态机+回读校验 | applyRule@537 + f5c8a0a7 |
| evolution 数据源 Agent OS 占位（0.05×i 冒充 fitness） | 2026-09-05 RFC 012 P2 切 v2 真实回测 | evolution 包注释 + 9/5 记忆 |
| learning_track 监听不存在的 tool/before-execute 事件 | 2026-08-20 改挂真实 waterfall post-execute | setupInterceptors@173 |
| backtest 随机 Sharpe / model 恒 0.4659 / M2-2 池刷假成功 | 9/5 审计另案（M 线）已列账 | profit-engine-completion-audit-20260905.md |

### 现存缺口与实证修正

**⚠️【审计纠错】初稿 G1（candidate 双轨脱节）撤回**——初稿误读了孤儿副本
- 真相：真实 genomeDir = `~/.dsh-agent-dh/genome/`（cordis.patch.yml genome 段显式配置，独立 git 仓库）；初稿读的 `~/.dsh/profiles/investment/data/candidates.json` 是 8/25 genomeDir 迁移前的**孤儿副本**
- 实证（真文件 candidates.json）：g19 R-011 候选**在册**——cand_1788573755281_v9g7aw（rules@g19 watching，created 2026-09-05T02:02:35.281Z = 10:02 北京，observe_until 09-10，health_check passed @ +27ms，mutation_type=prompt），与 genome git 提交 4627263（同秒 10:02:35 +0800）**双写同秒完成** → 9/3 修复后的 registerCandidate+genome_update 双写轨实际工作
- 9/5 19:32 gate 报告"候选总数 1（rules@g19 watching）观察期未满延期"**正确**（10:02 创建到 19:32 仅 9 小时 < 5 天观察期）；9/13 gate 应正常裁决 g19

**[F1] 文件状态可观测性空白（本次真发现，用户质疑落点）**
- genome.json / candidates.json / native-scheduler.json / restart-result.json 等全部本地文件 + 独立 git（genome 仓），**业务 DB（quant_investment，27+ 表）无 genome/candidates 表、无文件层错误通道**；DB 侧 error 落库只覆盖调度/服务层（task_runs.error 29 条实证）与 v2 system_logs
- 后果：语义故障（状态漂移、孤儿文件、空转）**不产生任何 DB 错误**——文件读写成功、工具返回 success，DB 无从感知；只能靠人工审计发现（本次即实证：孤儿副本误导审计，若无人工核对文件路径，错误结论已外发）

**[F2] 孤儿文件残留：`~/.dsh/profiles/investment/data/candidates.json`**
- 8/25 genomeDir 从 profile data/ 迁至 ~/.dsh-agent-dh/genome 后旧文件未清理；内含 1 条 8/25 测试残留 cand_test_strategy_bad（g13/过期）→ 排查/审计会被误导（本次审计即被其误导得出 G1 错误结论）；无自动清理/告警

**[F3] 调度 failed 窗口已过但缺周期检验**（记录非缺口）
- 9/2-9/4 全部 webhook 投递 failed（duration≈10s 超时，error 落库 29 条）——9/4 webhook 迁移阵痛期；9/5 起恢复
- 今天（9/6 周日）11:00 gate / 11:30 meta-learning / 12:00 weekly-report 为"skill 指引 + webhook 链路"下首次周度实战，是本报告的待验证点

## 三、证据清单

- E-1：genome history g19 stage=candidate git_commit=4627263（R-011，9/5 02:02 UTC = 10:02 北京）
- E-2：task_runs 9/5 10:00 evolution-weekly-variant scheduler success → 与 g19 时间吻合（端到端链路证）
- E-1：genome git 4627263（g19 R-011，9/5 10:02:35 +0800）+ candidates.json cand_1788573755281_v9g7aw（同秒 10:02:35.281Z，health_check +27ms passed）→ **双写同秒实证**
- E-2：task_runs 9/5 10:00 evolution-weekly-variant scheduler success → 与 g19 时间吻合（端到端链路证）
- E-3：真 candidates.json（~/.dsh-agent-dh/genome/）3 条：2 条已 promoted（8/25 裁决）+ g19 watching（9/10 观察期满）
- E-4：memory 86474aef gate 9/5 19:32 裁决记录："候选总数 1（rules@g19 watching）观察期未满延期"——与真文件一致，裁决正确（10:02 创建至 19:32 仅 9 小时 < 5 天观察期）
- E-5：enabled 任务 executor 分布：10 dsh-webhook + 7 空 + 0 dsh-native；native-scheduler.json lastFired 停 9/4 13:00
- E-6：孤儿文件实证：`~/.dsh/profiles/investment/data/candidates.json`（8/25 16:15 迁移前残留，1 条 g13 测试残留）vs 真文件（9/5 19:32 更新）——同路径不同内容，审计初稿被误导得出 G1 错误结论
- E-7：task_runs 9/2-9/4 failed（10s，error 落库 29 条）→ 9/5 success 迁移恢复曲线

## 四、修复建议（待确认后实施）

1. **[P1][F2] 清理孤儿文件**：删除 `~/.dsh/profiles/investment/data/candidates.json`（含测试残留）——它是 8/25 迁移残留，会误导审计/排查（本次实证）。
2. **[P1][F1] 补可观测性（回应"为何没报错到数据库"）**：文件层状态加健康哨兵——(a) 每轮 gate/进化任务核对 candidates.json 与 genome.json 的 candidate 一致性并在异常时 decision_audit+飞书（而非静默）；(b) 或把 genome/candidates 元数据镜像到 DB 表（quant 侧 genome_sections/candidates 2 表）供查询审计。推荐 (a) 轻量先行。
3. **[P2] 检验点**：9/13 gate 应裁决 g19（观察期满）——验证双写轨→gate 闭环端到端；若"继续观察"才是真断点，届时补裁。

## 五、与历次审计的关系

- 9/3 scheduler-autonomy-line-realization-audit：调度自动化线注册/投递层——本报告从代码+运行实证确认其"candidate→gate 真实编排"判定成立（g19 双写 + 9/5 gate 正确延期），并补其未覆盖的"文件状态可观测性空白"
- 9/5 profit-engine-completion-audit（w-8366e526）：M0-M8 盈利引擎完成度——本报告聚焦 L1-L4 Autonomy 线，互不重复

## 六、总判

Autonomy 线代码**无现存假实现壳、无断链**：4 处历史占位均已修复留痕；L1-L4 主体真实实现且有运行证据；进化闭环（蒸馏→registerCandidate 双写→gate 裁决）端到端工作——g19 双写同秒、gate 9/5 正确延期，9/13 观察期满应正常裁决。

**真实缺陷在可观测性层而非功能层**：genome/candidates 等关键状态存本地文件 + 独立 git，业务 DB 无表无错误通道——状态漂移/孤儿残留不产生任何 DB 错误，只能人工审计发现（本次审计即被 8/25 孤儿副本误导出错误结论后人工核对路径纠回）。修复优先级：F2 孤儿清理（顺手可做）> F1 可观测性哨兵（建议项）。
