# REQ-260925110957-552d REQ 实施链重构：ctx.jobs 异步化 + 写集并行 + 中断可续

> 状态：brainstorming（需求分析）｜ 类型：feature ｜ 难度：expert ｜ 创建：2026-09-25
> 立项来源：用户原话「问题收集完了，立项开始解决问题」，承接 REQ-260924213231-b1c4 归档后的实测诊断
> 证据基础：179 个会话 / 10,958 次工具派发的错误统计 + dsh-pmboard 源码逐条读码核对（本轮完成）

## 1. 需求概述

### 1.1 一句话目标

把 REQ 流水线的子卡执行从「一次工具调用同步跑完整条链」改成「注册后台任务、立即返回、跑完通知」，让拆分产物携带写集并按写集分批真并行，同时补齐中断恢复语义——`reqboard_task_run` 的 61.3% 失败率与「两个任务平行改同一文件就退化成串行」一并消除。

### 1.2 可证伪判定标准

- A1：mock 一张耗时 30 分钟的子卡 run，`reqboard_task_run` 调用 **< 1s** 返回 `status=dispatched` + `job_id`；不再出现 `execution deadline reached (120000ms)` 或 `tool call aborted`。
- A2：后台跑完后调用窗口收到会话内通知；`reqboard_run_status` 返回 `runId / 当前步 / 在跑子卡 / 下一步 / job 状态`，且与台账一致。
- A3：人为中断（abort 调用 + 模拟进程重启）后重入：孤儿子卡被回收或续跑，链能走到 rollup；断言**不出现** `noopStreak` → `PAUSE('stagnation')`。
- A4：恢复扫描（`scanAndResume`）能真的跑起一张子卡——断言不出现 `start_failed: Cannot read properties of undefined (reading 'session')`。
- A5：两张写集不相交的 ready 子卡 → 断言两个 workflow run 的执行时间窗**重叠**；写集相交 → 断言**不重叠**，且先后顺序写进 `decomposition.md`。
- A6：子卡产出走引擎 `schema` 结构化契约：通过校验的 run 必带 `filesChanged`；模型不按格式产出时不再「整卡静默失败」，而是引擎显式拒绝或降级为结构化空值并如实回报。
- A7：旧台账（`schemaVersion=7`、任务无 `filesPlanned`）读取后行为不变：视作「写集未知」→ 全串行，不报错、不硬拦。
- A8：真实会话回归：修复前后同一任务序列的 `tool call aborted` 计数归零；`reqboard_task_run` 失败率从 61.3% 降到个位数。
- A9：台账与看板能看到运行态（runId / 批次序号 / 在跑子卡 / 暂停原因）。
- A10：**交付生效可证伪**——`pnpm build` 后重启 profile，新增工具（`reqboard_run_status`）出现在工具表且可调用；`dist/index.mjs` 内能 grep 到新工具名；`lib/client.js` 不旧于 `src` 最新改动（与本仓既有 done 凭证门同源）。**不得只改 `src` 就宣称完成**。
- A11：**原生复用可证伪**——`reqboard_task_run` 投递后，原生 `job_list` 能看到 `kind=reqboard` 的 job（id 形如 `reqboard-N`，owner = 当前会话）；链跑完时收到**原生 completion notice**（`source.kind=plugin`、`form=notice`）；用原生 `job_kill` 终止时链在下一步停下并落台账（不停摆、不静默继续）。

### 1.3 背景与实测证据

统计口径：`.dsh-data/sessions` 下 179 个会话的 `tool/ptc-dispatch` 记录（近 4 天）。

| 观测 | 数值 |
|---|---|
| 总工具错误 | 455（4 天）/ 110（近 24h） |
| reqboard 工具族失败率 | ≈ 25%（read/edit/write/bash 仅 0.2%~4.7%） |
| `reqboard_task_run` | 19 错 / 31 调用 = **61.3%** |
| 其中 `tool call aborted` | 17 次，delta 稳定在 **595,364~595,467 ms** |
| `reqboard_ask_confirm` abort delta | 120,034 / 120,047 ms |
| `reqboard_capture` abort delta | 120,034 ms（本窗口活体复现一次） |
| 子卡层实际成功率 | 56 张子卡中 52 张 `lastRun.ok=true`、53 张产出非空 `filesChanged` |
| 引擎侧全局 run 超时 | **不存在**（`dsh-workflow-ptc` 只有 `syncTimeoutMs`=5s + maxConcurrentAgents/maxTotalAgents 上限） |

结论：死线**全部来自外层工具调用预算**，不是引擎或子卡设计的锅。

## 2. 现状调查（已核实代码，2026-09-25）

### 2.1 三条失败链

1. **同步长跑**：`advanceRequirement` 在一次工具调用里 `for i<20` 循环，每步 `RUN_SUBTASK` 里 `await workflow.start(...)` 等一整张子卡的 run。子卡实测 30s~10min+，2~3 张就撞穿调用方死线。设计文档其实已写对规则（`workflow-engine-contract.md` 踩坑表：「把长链塞进一个 run → 阻塞回合 + 10 分钟超时 → 一卡一 run，事件链分步」），实现违反了它。
2. **中断即停摆**：子卡在开跑**之前**就被写成 `in_progress`，而选择器只挑 `status==='todo'` 的卡 → abort 后孤儿卡**永不被选中** → 有 open work 却无可推进事件 → `noopStreak` 累到 5 → `pauseRequirement('stagnation')` 且 `autoRun=false` → 链永久停摆，需人工捞。
3. **并行是假的**：`advanceMaxParallelParents=3` 只影响「几张父卡算 in_progress」；执行器一次只返回**一个**事件、只跑第一张 ready 子卡 → 实际执行永远串行。跨卡同文件还会被 `detectCrossCardOverwrite` 判成**失败**——因为系统没有「写集」概念，分不清两张卡到底会不会打架。

### 2.2 代码坐标汇总

| 问题 | 坐标 | 现状 |
|---|---|---|
| 事件链塞进一次调用 | `application/use-cases/AdvanceChain.ts`（主循环）· `domain/limits.ts` `advanceMaxStepsPerCall=20` | 同步跑最多 20 步，撞穿 120s/600s |
| 每步同步等整张子卡 | `application/use-cases/ExecuteTask.ts` `deps.workflow.start(...)` | 一卡一次 run，run 完才继续 |
| 先认领后执行 | `ExecuteTask.ts`（`subtask-started` 写 in_progress） | 中断即孤儿 |
| 选择器只认 todo | `application/internal/advance-select.ts`（ready 子卡过滤） | 孤儿卡不可选 → 停摆 |
| 恢复扫描缺 parent | `AdvanceChain.ts` `scanAndResume` 不传 exec → `ExecuteTask.ts` `parent: exec.agent` = undefined → `dsh-workflow-ptc` 读 `request.parent.session` 抛错 | 「崩溃不丢链」恢复路径必然失败 |
| 产出靠提示词约定 | `application/internal/workflow-script.ts` 只传 prompt · `ExecuteTask.ts` 要求「只输出一个 JSON 对象」 | 引擎原生 `agent(prompt,{schema})` 未使用 |
| 并行能力闲置 | 脚本只用 `agent()`，引擎的 `parallel()/pipeline()` 一次没用 | 一卡一 run、宿主串行派发 |
| 失败即暂停 | `AdvanceChain.ts` `classifyFailure` → `pauseRequirement` | 不区分「可重试」与「真做不出来」 |

### 2.3 调查结论

一句话根因：**子卡切分与闸门是对的（52/56 成功），坏的是「怎么驱动它」——把它当成同步、一次性、不可恢复的操作。** 因此要改的是驱动层，不是重写子卡。

### 2.4 第 4 条：部署缺环（本轮新发现，且已经造成过实际损失）

`dsh-pmboard` 的 `package.json` 是 `"main": "./dist/index.mjs"`——**插件是从构建产物加载的，不是 tsx 直载 TS 源码**。因此「改 src → 重启」并不生效，必须 **`pnpm build` 之后再重启**。

实测现状（2026-09-25）：

- `dist/index.mjs` 构建于 **Sep 24 14:54:07**，而 b1c4 的源码改动是 **Sep 25 02:22:16**；profile 重启于 **02:27:42**。顺序对了、**构建缺了**。
- 硬证据一：运行中的工具表里**没有** `reqboard_confirm_receipt`（b1c4 新增）；`dist` 里 grep 该名字 **0 命中**，`src` 里有。
- 硬证据二：`dist` 注册 13 个 reqboard 工具，`src` 注册 15 个（缺 `reqboard_confirm_receipt`、`reqboard_note_interruption`）。
- 结论：REQ-260924213231-b1c4 的 FR-3（弹框非阻塞 + 挂起回执）**从未上线**——它要修的东西正是本需求 FR-1 要绕开的那个 120s 死线。

因此本需求把「构建 + 重启 + 工具表可见」纳入交付判据（A10），避免同类返工。

**欠账处理留痕（已闭环）**：2026-09-25 11:12 补构建 `packages/web/dsh-pmboard`（工作区干净，src == HEAD `ec69a758`）——
`dist/index.mjs` 与 `lib/client.js` 重建（mtime 11:12:57），reqboard 工具数 **13 → 15**（补齐 `reqboard_confirm_receipt`、`reqboard_note_interruption`），
`dist` 内可 grep 到 `reqboard_confirm_receipt`（12 处）/ `reqboard_note_interruption`（10 处），且无 `src` 文件新于产物。

**重启已执行并活体验证**：同日经 `quick_restart` 重启 profile 后，本窗口工具表已出现 `reqboard_confirm_receipt`；
以不存在的 ticket 调用它，返回的是结构化错误 `REQBOARD_UNKNOWN_TICKET`（而非「未知工具」）——
证明 REQ-260924213231-b1c4 的 FR-3（弹框非阻塞 + 挂起回执）**现已真正上线**，欠账闭环。
本需求仍把「构建 + 重启 + 工具表可见」固化为交付判据（A10），防止同类缺环再次发生而不被察觉。

**证据附件（可复跑）**：[deploy-verification-2026-09-25.md](deploy-verification-2026-09-25.md)——含构建/重启/活体工具表三段命令与原始输出、时间链（构建 11:12:57 → 重启 11:15:02 → 新进程 11:15:14 → ok 11:15:16）、复跑方式。

### 2.5 DSH 原生能力盘点：哪些直接用原生，哪些必须自研

> **结论先说：后台执行不自己造 —— 用 DSH 原生 `ctx.jobs`；我们只写 REQ 语义的薄适配层。**
> `reqboard_task_run` 的职责是「把一条 REQ 子卡链注册成 `kind=reqboard` 的后台任务并立即返回」，
> **不是自研调度器**；跑完通知、任务列表、读取、终止全部复用宿主已有能力。
>
> **文档分工（本节读法）**：本节只回答「有没有原生、能不能用」——属**选型依据**（需求阶段）。
> 表中「我们怎么用」一列的**调用签名、循环结构、调度算法、错误处理**属**落地形态 = 设计**，在 design 节点展开。

**直接复用（一行都不自己写）**

| 原生能力 | 出处（0.1.6-alpha.2，已读码核对） | 我们怎么用 |
|---|---|---|
| 后台任务注册：`start/list/get/read/kill/wait/onJobDone/onJobsChanged/attachController` | `@deepseek-ai/dsh-jobs` `lib/types/index.d.ts`（Abstract `JobRegistry`，注册名 `ctx.jobs`） | FR-1 调 `ctx.jobs.start({ kind:'reqboard', owner, label, run })`，同步拿到 `<kind>-N` id 后**立即返回** |
| 归属与隔离（owner = 会话，按 session id 围栏；"Ids are predictable, so authorization — not secrecy — is the boundary"） | 同上 | job 归属 = 启动它的 agent，沿用 §7 既有约定 |
| 完成通知唤醒会话 | `@deepseek-ai/dsh-tool-jobs` `lib/index.js`：`attachController("tool-jobs")` → `onJobDone` → `createUserMessage(source.kind='plugin', form='notice')` → `owner.followup(message)`（idle+wakeup）/ `owner.inject(message)` | **直接复用**：跑完由原生 notice 唤醒会话，不自建通知通道（A2 判据由此满足） |
| 任务列表 / 读取 / 终止工具 | `job_list` / `job_output` / `job_kill`（已在工具表） | agent 排障与收尾直接用原生工具 |
| 子卡执行引擎 | `dsh-workflow-ptc`（workflow run；`agent(prompt,{schema})`、`parallel()`） | FR-7 用引擎 schema 产出、FR-4 用引擎侧并发原语 |
| 生产者范式（照抄对象） | `@deepseek-ai/dsh-tool-bash`：`jobs.start({ kind:'bash', label, owner: exec.agent, run })` 后立即返回 `{kind:'background', jobId}` | 与 FR-1 的「投递回执」形态**逐字同构**，实现时照此写 |

**必须自研（宿主不可能提供，属 REQ 语义）**

- 认领与幂等（同一父卡重复投递不重复起 run）；
- 写集分批调度（批内并发 / 批间串行，目录前缀计入冲突）；
- 孤儿回收与 resume（选择器补 resume 分支）；
- 台账 checkpoint 与运行态投影（runId / 步号 / 心跳 / 当前子卡）；
- 阶段闸门与产物确认（`reqboard_*` 既有能力）。

**两条最容易搞混的边界（先写死，免得实现跑偏）**

1. **`reqboard_run_status` 不是自建轮询**：原生 `job_list/job_output` 只回答「job 跑成没跑成」，
   回答不了「当前步 / 在跑子卡 / 下一步 / 写集冲突 / 暂停原因」。FR-2 是**投影**（原生快照 + 台账合成），不新增执行或轮询机制。
2. **链的推进必须在后台 run 内部循环，不能依赖「会话被唤醒后再推下一步」**：否则调用方一 abort 就无人唤醒，
   又回到 §2.1 的停摆（A3 必红）。原生 notice 的职责是**告知结果**，不是**驱动链**。

**为什么不用 `subagent` 等原生委派直接替代 `reqboard_task_run`**：`dsh-tool-subagent` 同样走 `jobs.start`（机制同源），
但它只提供通用委派，没有 REQ 台账、写集、孤儿与闸门语义——直接拿它替代，§2.1 的三条失败链会原样复发。
所以保留薄封装：**机制全用原生，只自研语义**（封装成本 ≈ 一次 `start` 调用）。

### 2.6 决策对比：薄壳（A）vs 裸用原生（B）vs 薄壳精简（C）

**先把问题问对**：机制层面三者没有分歧——都建立在原生 `ctx.jobs` 上。
真正的分歧只有一个：**「链循环归谁」**——由代码在后台 job 里跑完，还是由模型一个回合一个回合地手动编排。

| 维度 | **A 薄壳 + 原生机制（推荐）** | **B 裸用原生（模型手动编排）** | **C 薄壳但不新增查询工具** |
|---|---|---|---|
| 链循环归属 | 代码（job 内 loop） | 模型（每回合派一步） | 代码 |
| 一次投递能推几步 | 到跑完/暂停（上限内） | 1 步 | 到跑完/暂停 |
| 模型注意力 / Token | 只在结束时被唤醒 | **每步一次唤醒 + 一次决策** | 同 A |
| 写集分批（FR-4） | 代码实现，可单测 | 靠模型每回合心算，不可复现 | 同 A |
| 中断可续（FR-3 / A3） | 台账 checkpoint + 启动扫描 | **无落点**：原生 registry 是进程内的 | 同 A |
| 认领幂等（FR-1） | 认领 + 投递原子完成 | 多窗口可能重复派同一张子卡 | 同 A |
| 孤儿回收（FR-5） | 选择器补 resume 分支 | 无落点，卡仍「选不中」→ 停摆 | 同 A |
| 运行态可查（FR-2 / A9） | 专用**只读**快照，不消费 job 读游标 | 仅原生 `job_output`，有吞通知风险（见下） | 进程写进 job 输出流，同样有该风险 |
| 新增工具面 | +1（`reqboard_run_status`） | 0 | 0 |
| 修复父级归属（FR-6） | 需修 `scanAndResume` 透传 exec | 原生 `subagent` 自带 parent（此点 B 更省） | 同 A |

**B 会失去什么（逐条对着 §2.1 的实测证据）**

1. **中断即停摆修不掉**：原生 job 注册表是**进程内**的（`@deepseek-ai/dsh-jobs` 原文："The process-local registry lives in `@deepseek-ai/dsh-jobs-local`"），进程重启后 job 记录消失。
   「崩溃不丢链」只能靠**我们自己的台账 + 启动扫描**——B 没有这个落点，A3 永远红。
2. **并行仍然假**：谁跟谁不能同时改同一文件是**文件事实**，不是模型每回合的心算。交给模型 → 不可复现、不可单测，`detectCrossCardOverwrite` 的误判照旧（§2.1-3）。
3. **认领无闸门**：两个窗口/两次调用可能同时认为「这张卡该我跑」。A 用「认领 + 投递原子」消除（FR-1）。
4. **台账要模型自己记得写**：`todo→in_progress→…→done`、全 done 自动进验收，B 里全靠模型每回合自觉；漏一次就是 §2.1-2 的停摆。

**B 的真实好处（也要说清）**：少写代码、少一个工具；异步/通知/取消全用原生，没有自研 async 管道的出错面；模型可在链中途换策略。
> 但 §2.1 的实测证据恰恰表明：这三条失败链的根因就是**把长链的执行责任交回给模型回合**（调用预算 120s、abort 后无人推进）。在这里，灵活性是负债而非资产。

**C 的技术隐患（所以不推荐）**：原生 `read` 的**终态读会标记 job 为 reported**，而 `dsh-tool-jobs` 的完成监听器第一句就是
`if (snapshot.reported || owner === void 0) return` —— 先用 `job_output` 读终态，可能**吞掉完成通知**。运行态查询应当用
**不消费读游标**的 `ctx.jobs.get()`（d.ts 原文："a non-consuming snapshot without changing its read cursor or notice state"）。
**这正是 A 要新增一个只读查询工具的理由，而不是重复造轮子。**

**结论**：A = 机制全用原生 + 只自研 REQ 语义；B = 放弃本需求的大半（FR-1/2/3/4/5/9 失去落点）；C 省一个工具但踩原生 reported 语义。
推荐 **A**。

**文档分工（回应「这个写需求还是写设计」）**

- 本仓 feature 档**明确要求需求阶段就写**「接口契约 / 数据契约 / 验收怎么跑」（即 §7 / §8），流水线又把 brainstorming 的职责定义为「探边界 / **方案**」——
  所以**方案选型结论（A）与判据（A1–A11）留在需求**，它们是设计的输入约束。
- **实现形态进设计**：`ctx.jobs.start` 的调用签名与 spec 形状、后台 run 内的循环结构、写集分批算法、`ctx.jobs.get()` 与 `job_output` 的取舍、错误码与降级路径、测试替身设计。
- 因此 §2.5 / §2.6 是**选型依据**（现状 + 决策记录），不是设计正文；design 节点会据此产出
  `docs/requirements/<REQ>/design/` 下的架构 / 接口 / 数据模型 / 测试用例文档，并把本节的结论收敛为引用。

## 3. 产品定义

- 产品名称：REQ 流水线（项目看板 dsh-pmboard 的 reqboard 工具族 + 实施链执行器）
- 类型：内部工程平台能力（面向 agent，不面向终端用户）
- 定位：把「需求分析 → 设计 → 拆分 → 实施 → 验收」的阶段纪律，做成 agent 与人都不空转的闸门与执行链
- 核心价值：实施链不再因调用预算而中断、不再因中断而停摆、并行度由文件冲突客观决定

## 4. 用户与角色

- 主用户：DSH 窗口里的 agent（唯一会调 `reqboard_*` 的主体）——需要「投递后不用原地等」的调用语义与「跑完了谁通知我」的确定路径。
- 次用户：投资人（人）——只在需要裁决时被打扰；不该因为链中断就去手动捞卡。
- 维护者：本仓开发者——需要这些不变量被 vitest 锁死，避免回归（写集分批、孤儿回收、schema 产出）。

## 5. 边界

**做什么：**

- 只动 REQ 流水线的驱动面：执行链（AdvanceChain/ExecuteTask）、子卡调度与选择器、拆分产物（写集声明）、`reqboard_task_run` 工具契约与新增运行态查询、台账字段与迁移、阶段提示词、以及看板运行态呈现。
- 每项改动自带可回归的 vitest 用例（本仓已有 `packages/web/dsh-pmboard/tests/`）。
- 借 DSH 自带能力承载后台执行（`ctx.jobs` / `dsh-tool-jobs` 的完成通知），但**不修改 DSH 包**。
- 交付口径收紧：本插件的生效路径是「构建 → 重启」（A10），交付时必须走完，不得以「源码已改」作为完成依据。

**不做什么：**

- 不改宿主 `@deepseek-ai/dsh-*` 包，尤其不改 `run_code` 的 120s/600s 预算——只**绕开**它，不试图说服它。
- 不改流水线阶段划分，不放松任何人工闸门（「该不该拦」的判定标准不动）。
- 不重写子卡本身的设计（叶子在 workflow、枝干在宿主的切分保留），不重写 workflow 脚本契约门禁。
- 不改变 `reqboard_*` 既有工具的参数语义（除非本需求显式声明的那个：`reqboard_task_run` 的返回语义由「终态」改为「投递回执」）。
- 不做节点隔离（NODE_ISOLATION）与压缩链的调整，不重构无关模块。
- 不自研后台任务系统：后台执行一律复用原生 `ctx.jobs`（机制全原生，只自研 REQ 语义——台账/写集/孤儿/闸门）；亦不得退化为「同步跑完才返回」的旧形态。

## 6. 功能点

- **FR-1: reqboard_task_run 改为投递式调用**
  现状：一次调用同步跑完整条链（最多 20 步），必撞调用方预算。
  目标：工具只做校验 + 幂等认领 + 注册后台任务（**复用原生 `ctx.jobs.start`**，不自建任务系统），**立即返回**；认领与投递原子完成，重复调用不重复起 run。
  验收：A1。

- **FR-2: 新增运行态查询入口 reqboard_run_status**
  现状：只有终态返回，中途无任何可查询面，agent 只能靠猜。
  目标：给定需求或 runId，返回运行态快照（runId、当前步、已跑完子卡、在跑子卡、下一步、job 状态、暂停原因、autoRun）——本质是**原生 job 快照 + 台账的投影**（见 §2.5），不新增执行/轮询机制。
  验收：A2。

- **FR-3: 后台执行与调用生命周期解耦**
  现状：执行挂在调用方的 async 栈上，调用方一超时（或任何 abort）全链陪葬。
  目标：执行器持有自己的取消信号与预算；每步落 checkpoint 到台账（runId / 当前子卡 / 步号 / 心跳）；进程重启后由启动扫描从 checkpoint 续跑，而不是从头或永远停住。完成通知**复用原生 `dsh-tool-jobs` 的 `onJobDone` → `followup/inject`**（见 §2.5），不自建通知通道。
  验收：A3、A8。

- **FR-4: 拆分产物声明写集，调度按写集分批（真并行）**
  现状：并行只在台账上存在，执行永远串行；同文件冲突被当作失败。
  目标：拆分阶段为每张卡声明写集（`filesPlanned`）；调度把 ready 子卡按「写集两两不交」分组，**批内并发、批间串行**；目录前缀计入冲突；未声明文件仍走现有兜底；先后顺序写入 `decomposition.md`，让拆分产物自己说清「共享文件谁先谁后」。
  验收：A5、A7。

- **FR-5: 子卡中断可续（孤儿回收 + resume 语义）**
  现状：子卡被认领即 `in_progress`，而选择器只挑 `todo` → 中断产生的孤儿卡永不被选中 → `noopStreak` 到 5 → 停摆。
  目标：超阈值且无活跃执行的 `in_progress` 子卡判为孤儿，退回 `todo`（`attempt+1`，走既有回滚路径）或按 resume 重新认领；选择器补上 resume 分支。任何一次中断都不再留下「选不中的卡」。
  验收：A3。

- **FR-6: 恢复路径的 parent 透传修复**
  现状：`scanAndResume` 不传 exec → `parent=undefined` → 引擎同步抛 `start_failed: Cannot read properties of undefined (reading 'session')`，恢复扫描注定跑不通。
  目标：恢复路径拿到合法的执行归属（透传 exec，或为 system 驱动的恢复提供一个引擎接受的 parent）；失败不再以「缺 parent」形式出现。
  验收：A4。

- **FR-7: 子卡产出改为引擎结构化契约**
  现状：脚本只传 prompt，产出格式靠提示词约定 + 事后解析；模型不照格式即整卡失败。
  目标：使用引擎原生 `agent(prompt, { schema })` 的结构化产出能力（引擎会做 schema 校验并返回结构化对象）；`filesChanged` 由此获得硬保证，不再依赖模型自觉。
  验收：A6。

- **FR-8: 工具契约与提示词同步更新**
  现状：旧提示词把 `reqboard_task_run` 当作「跑完才返回」，语义一变会诱导模型把 `dispatched` 当 done。
  目标：工具 description、阶段提示词、兼容别名 `reqboard_task_execute` 同步说明新语义（投递 ≠ 完成；跑完由通知唤醒，用运行态查询取回执）；提示词基线快照测试更新。
  验收：A1、A2。

- **FR-9: 运行态可观测**
  现状：链在后台跑时，台账与看板都看不出「跑到哪、卡在哪」。
  目标：台账记录运行态（runId / 批次 / 在跑子卡 / 暂停原因），看板据其渲染；同一会话回归可复核「工具错误率」这一诊断指标。
  验收：A9、A8。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |
| FR-5 | 🔴 **未被接收** | — |
| FR-6 | 🔴 **未被接收** | — |
| FR-7 | 🔴 **未被接收** | — |
| FR-8 | 🔴 **未被接收** | — |
| FR-9 | 🔴 **未被接收** | — |

> 🔴 **未被接收（9 条）**：FR-1、FR-2、FR-3、FR-4、FR-5、FR-6、FR-7、FR-8、FR-9

<!-- reqboard:marks:end -->

## 7. 接口契约（对外入口）

- `reqboard_task_run(task_id)`：入参不变（父卡 id）。出参新增/变更：`status ∈ {dispatched, running}`、`job_id`、`run_id`、`running[]`、`next_ready[]`，保留 `success / task_id / requirement_id`。错误语义保持既有码（任务不属于本窗口绑定的需求、任务不存在等），新增「后台任务不可用/超并发上限」的显式失败码，**不得静默降级为同步执行**。
- `reqboard_run_status(requirement_id? | run_id?)`：只读；缺参时默认本窗口绑定的需求。出参含运行态快照；无在跑 run 时返回终止态与原因，不报错。
- `reqboard_task_execute(task_id)`：兼容别名，语义与 `reqboard_task_run` 等价。
- 后台任务命名与归属：kind 固定为 `reqboard`，id 形如 `reqboard-N`；归属启动它的 agent 会话（沿用 DSH 的 job 归属规则）。

## 8. 数据契约与迁移

- `TaskRecord` 新增可选字段 `filesPlanned?: string[]`（写集；缺省 = 未知 → 调度器退化为全串行）。声明粒度：工作区相对路径或目录前缀。
- `RequirementRecord.advance` 新增运行态字段：`runId?`、`currentSubtaskId?`、`stepIndex?`、`heartbeatAt?`；与既有 `lockAt` 并存（`lockAt` 语义改为心跳，stale 可接管）。
- 子卡新增 `attempt` 语义沿用既有字段，不新增重复计数。
- **迁移**：`REQBOARD_SCHEMA_VERSION` 由 7 递增；读旧台账时新字段全部按缺省处理（旧行为不变），不做破坏性重写；删除/回滚本需求后，新字段被忽略即可回到旧行为（无单向数据变换）。
- **兼容**：旧调用方拿到 `dispatched` 后若按旧语义轮询，可由 `reqboard_run_status` 满足；提示词同步后不再鼓励轮询。

## 9. 验收怎么跑

- 单测（纯函数为主，无需真引擎）：写集分批与目录前缀冲突、孤儿回收阈值、选择器 resume 分支、迁移缺省、出参契约。
- 引擎替身：注入一个可控时长的 mock `WorkflowRunner`（例如 30 分钟），断言 A1 的 < 1s 返回、A5 的时间窗重叠/不重叠、A6 的 schema 产出路径。
- 中断回归：构造 abort + 重新加载台账两条路径，断言 A3/A4（不出现 stagnation、不出现 `start_failed`）。
- 现场复核：抓取修复后同一批会话的 `tool/ptc-dispatch` 记录，统计 `reqboard_task_run` 失败率与 `tool call aborted` 计数（A8）。
- 命令锚点：`cd packages/web/dsh-pmboard && npx vitest run`（全绿，含新增用例）；`npx tsc --noEmit -p tsconfig.json`（0 错误）。
- 生效锚点（A10）：`pnpm build`（host → `dist/index.mjs`，client → `lib/client.js`）→ 重启 profile → 断言工具表出现 `reqboard_run_status`；并比对 `dist/index.mjs` 的 mtime 不旧于 `src` 最新改动。