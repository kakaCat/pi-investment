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
| **L4** validation_gate | ✅ 真（工具本体） | ValidationGateTool：读 candidates.json + searchRewards 打标经验对比（q=`genome:${version}` kind='experience'）+ L4-B 结构防御 + min_samples=3 延期 | 9/5 19:32 真实执行（memory 86474aef）；但裁决对象错位见 G1/G2 |
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

### 现存缺口（本次新发现）

**[G1] 候选登记双轨脱节：genome_update(stage='candidate') 不写 candidates.json → validation_gate 无门可裁** ⚠️ 半通
- 代码实证：packages/evolver/src/candidates.ts L5-6 注释自白——"genome_update(stage='candidate') 只写 genome.json history、从不写 candidates.json，ValidationGateTool 读 candidates.json 永远无输入 → 验证门空转（'候选 0'实证坐实）"
- 运行实证：g19（rules candidate，2026-09-05 10:02 variant 真实产出，genome_history stage=candidate）**不在** candidates.json（该文件仅 1 条 8/25 测试残留 g13）；validation_gate 9/5 19:32 裁决对象实际是那条 g13 测试残留（样本不足延期），报告却写"rules@g19 watching"——agent 把 genome 版本状态拼进了裁决汇报，g19 从未真正被 gate 读过
- 后果：9/13 gate 跑时 g19 观察期满（9/10）仍无门可裁 → 自动化"蒸馏→观察→裁决→转正/回滚"闭环对 agent 直写轨候选永不生效
- 已规避路径：prompt_evolver 9/3 修复为双写（registerCandidate + genome_update）✓；未规避路径：engine-heal-evolve skill 指引 agent"单主题 genome_update(candidate)"（g19 即此轨产物，任务 prompt 9/5 22:12 挂载）

**[G2] candidates.json 唯一候选是 8/25 测试残留，自动化候选流水线 12 天空转**
- cand_test_strategy_bad（rules@g13 watching，observe_until 2026-08-24 已过期，note="测试回测腿拒绝路径"）——过期 12 天无人清理；9/5 gate 还在对它做"样本不足延期"
- 8/25（g14 promote）→ 9/5（g19 candidate）之间 11 天，candidates.json 零新候选登记

**[G3] 调度 failed 窗口已过但缺周期检验**（记录非缺口）
- 9/2-9/4 全部 webhook 投递 failed（duration≈10s 超时）——9/4 webhook 迁移阵痛期；9/5 起恢复
- 今天（9/6 周日）11:00 gate / 11:30 meta-learning / 12:00 weekly-report 为"skill 指引 + webhook 链路"下首次周度实战，是本报告的待验证点

## 三、证据清单

- E-1：genome history g19 stage=candidate git_commit=4627263（R-011，9/5 02:02 UTC = 10:02 北京）
- E-2：task_runs 9/5 10:00 evolution-weekly-variant scheduler success → 与 g19 时间吻合（端到端链路证）
- E-3：candidates.json 全文仅 1 条 cand_test_strategy_bad（g13/过期/watching）
- E-4：memory 86474aef gate 裁决记录（"候选总数 1 rules@g19 watching...继续观察"）vs 实际裁决对象 g13 测试残留 → 报告错位实证
- E-5：enabled 任务 executor 分布：10 dsh-webhook + 7 空 + 0 dsh-native；native-scheduler.json lastFired 停 9/4 13:00
- E-6：candidates.ts L5-6 注释（问题自白）+ f5c8a0a7/aa1213c4（9/3 修复提交）
- E-7：task_runs 9/2-9/4 failed（10s）→ 9/5 success 迁移恢复曲线

## 四、修复建议（待确认后实施）

1. **[P0][G1] 统一候选轨**：二选一——(a) genome_update(stage='candidate') 内部同步写 candidates.json（需 genome 包获 observeDays/note 参数，或从 genome.json candidate 段反向登记）；(b) validation_gate 增加 genome history stage=candidate 读取源。推荐 (b) 副作用小：gate 裁决 = candidates.json ∪ genome candidate 段。
2. **[P1][G2] 清理测试残留**：cand_test_strategy_bad 置 rejected/drop（已过期 12 天，note 明确是测试）；顺手把 8/25 后无真实候选的"空转"写入记忆供复盘。
3. **[P1] engine-heal-evolve skill 校准**：若走 genome_update(candidate) 直写，须配套 gate 双源读取（即 1b），或改指引为 prompt_evolver 双写路径。
4. **[P2] 检验点**：9/13 gate 应裁决 g19（观察期满）——若仍"继续观察"即 G1 未修复的实锤，修复后补裁。

## 五、与历次审计的关系

- 9/3 scheduler-autonomy-line-realization-audit：调度自动化线注册/投递层——本报告补其未覆盖的"candidate 轨对齐"（9/3 判 candidate→gate 真实，实为双轨）
- 9/5 profit-engine-completion-audit（w-8366e526）：M0-M8 盈利引擎完成度——本报告聚焦 L1-L4 Autonomy 线，互不重复

## 六、总判

Autonomy 线代码**无现存假实现壳**（4 处历史占位均已修复留痕）；L1-L4 主体为真实实现且有运行证据。**但自动化进化闭环存在 1 处实质断点（G1 candidate 双轨脱节）**：工具本体都真，轨没对齐 = "半通"而非"假"——进化候选（g19）与裁决入口（candidates.json）各走各的，验证门对 agent 直写轨候选实际空转。这与"引擎进化每周一轮"的设计目标不符，属交付前需修复项。
