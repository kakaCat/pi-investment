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

## 七、F1/F2 落地执行记录（2026-09-06 10:15 补充，w-a8a89c6a）

### F2 孤儿文件删除（已完成）
- 删除 `~/.dsh/profiles/investment/data/candidates.json`（8/25 迁移残留，仅 1 条 g13 测试残留）；删除前精确复核源码/配置无指向该路径的 candidates.json 引用（grep --include 源码类型，排除 node_modules/dist 压缩产物）。
- 备份 `/tmp/orphan-candidates-20260825-backup.json`；决策留痕 DEC-20260906100044-851ba11f（audit_finding）+ memory dcfbc10b。

### F1 可观测性完善 A+B 两步走（已完成）
- **A 步（零代码 SOP，commit 72e082b9）**：`agent-dh/skills/engine-heal-evolve/SKILL.md` 新增第 4.5 步"状态一致性核验（F1 哨兵）"——genome_benchmark() 拿候选清单 W → genome_history 拿 H → C2 登记缺失检测（history stage=candidate 无 candidates.json 对应）→ C3 过期待裁检测 → 异常落 decision_audit + 飞书 alerts high（影响裁决时）/静默。skill 经软链装载（repo 真身即实例生效），4 个进化类 Agent 任务 prompt 全部委托该 skill → 一处修改全局生效。
- **B 步（ValidationGateTool 诊断腿，commit 054f7d07）**：`runConsistencyCheck()` 每轮 gate 裁决前核验 candidates.json ↔ genome.json history：
  - C1 孤儿候选：watching 候选 genome_version ∉ genome history（promote/rollback 无依据）
  - C2 未登记版本：history stage=candidate 无 candidates.json 对应（registerCandidate 断链，验证门无案可裁）
  - C3 原子写残留：genomeDir 下 *.tmp
  - healthy=false → summary 警告 + consistency 明细字段，促执行方 decision_audit 落 DB（文件层故障从此有 DB 痕迹）
  - 单测 6/6（tests/gate-consistency.test.ts，worktree feat/f1-gate-consistency 开发合并）+ 既有 gate/candidates 回归 8/8
- **B 步实测实证（重启 13080 加载新代码后）**：validation_gate 首跑即捕获 **C2 g16**（principles v6@8/28 应用，stage=candidate 滞留 9 天，candidates.json 无登记——9/3 registerCandidate 接回前的历史 bug 真实残留，观察版从未被 gate 裁决却持续实际运行）。g16 内容=8/28 P0 工具循环事故修复的原则#5（todo_write+3次熔断），9 天实际运行验证有效 → **genome_promote(principles) 转正（git 6246cc5）** → 复跑 validation_gate consistency.healthy 归零。端到端闭环：异常→捕获→确定性处置→复验归零，全程落 decision_audit DEC-20260906101443-5026baca + memory 6289225c。
- **C 步（DB 镜像）未实施**：agent-dh 无 pg 通道，暂缓（A+B 已覆盖"异常必留痕"目标）。

### 遗留检验点
- 9/10 g19（R-011）观察期满 → 9/13 gate 应裁决转正/回滚：届时 consistency 诊断腿全程监控，是双写轨→gate→裁决闭环的端到端检验点。

## 八、「自主进化」看板交付：Autonomy 线能力设计层 GUI 化（2026-09-06 10:45，w-a8a89c6a）

### 背景
第六/七节判定"真实缺陷在可观测性层"、F1 哨兵（A skill 步 + B gate 诊断腿）落地——但哨兵是"Agent 看得见的健康检查"，用户仍无可视化窗口。本交付把 Autonomy 线**能力设计层**（genome 段状态/候选生命周期/谱系/C1-C3 一致性）做成 DSH GUI 页面「自主进化」，独立看板（非扩展智能执行），回答：改了什么规则/什么在试运行何时出结果/进化链路有无卡住。

### 交付物
- 新包 `agent-dh/packages/pages/genome`（@pi-investment/dashboard-genome），双半插件模式同 execution：
  - host 半（cordis 插件）：`/dashboard/api/genome` kind:exact 注册，fs 直读 genomeDir（genome.json+candidates.json）聚合 5 区域 JSON
  - client 半（lib/client.js 构建产物入库）：顶部 logoRow DOM 入口「自主进化」+ 30s 轮询 + 候选 tab 过滤（全部/watching/到期/promoted/rejected）+ 重检按钮 + 被动互斥（与 execution/holdings/bulletin 面板互斥激活）
  - 5 区域单页：①基因组段总览（constitution 锁定/evolvable 版本+最近变更）②候选生命周期（watching 进度条/观察期剩余/结构健康徽章/到期⏰ 高亮）③C1-C3 一致性哨兵（与 gate runConsistencyCheck 同源，healthy 徽章）④谱系时间线（22 条 history，gN/vN/type/commit/理由）⑤元信息+重检
- README 写清与 execution 看板互补关系（execution=双线执行确认，genome=进化链路自身健康）

### 排障记录：404 根因 = 注册改错目录（重要教训，跨会话防再踩）
- 症状：`/dashboard/api/genome` 稳定 404、`/dashboard/api/board`（execution）200 → host 半机制本身有效，先疑代码后穷举环境
- 排除：非旧进程（两次重启仍 404）、非 YAML 缩进（cat -vet 字节级核对）、非 import 能力（同构依赖 tsx）、非 package.json 差异（diff 一致）
- **根因**：改错了注册目录。运行实例 dsh 从 **$DSH_HOME** 解析 profile 配置目录 = `~/.dsh-agent-dh/profiles/investment`（真身：cordis.patch.yml/package.json/node_modules 都在这里改才生效）；`~/.dsh/profiles/investment` 只是安装/启动目录（进程 cwd 误导——bin 从 A/node_modules 启动但 profile 数据在 B）。实证手段：`dsh --dump-config` 打印合并树，404 时 dump 无 dashboard-genome → 定位改错目录（在 B 补注册三处后 dump 含 genome → 重启即 200）
- 另证 client 半发现机制：dsh-client-modules 扫 host Loader entries（cordis 插件树）声明 dsh.client 的包 → host 加载后 client 自动入图；missing bundle 会 loud throw 启动失败，启动成功即 bundle 完整
- 遗留清理：A（~/.dsh/profiles/investment）三处误导注册已还原（patch/package.json 0 命中，软链保留指主仓无害）；两处 node_modules 软链均改指主仓

### 验证与收尾
- `/dashboard/api/genome` 200：g20 | 4 sections（constitution v1 locked + principles v6/rules v9/lessons v7 带 lastChange）| consistency healthy（C1/C2/C3 issues 空）| 3 candidates（2 promoted lessons + 1 watching rules g19 v8 cand_1788573755281 观察期 9/10 到期）| history 22 条
- 契约核对：服务端聚合输出 ↔ client view 字段逐一比对通过（section.id/lastChange、consistency.issues[].items、candidate.healthCheck 守卫、history.genomeVersion）
- 合 main 704fd03c（worktree feat/dashboard-genome → merge，仅 genome 包 19 文件，无 IP/端口改动），worktree 已删、branch 已删
- 决策留痕 DEC-20260906104011-7ec4c8e3 + memory 994ce3d2（$DSH_HOME 配置目录真相，importance 0.85）
- GUI 目验待人工：刷新 http://127.0.0.1:13080 侧栏顶部「自主进化」→ 5 区域渲染 + 候选 tab 过滤 + 重检
