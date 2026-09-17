# REQ-422af1 节点提示词按路径分层注入（对齐 superpowers Three Paths）

> 状态：需求分析（brainstorming）· 窗口 w-41e7e4cd · 立据：用户 2026-09-17
> 宣布路径：**Architectural**（新增注入机制 + 改取词结构 + 涉及多文件）——按用户认可的口径，本需求走完整流程。

## 1. 背景与动机

用户要求（原话）：

> 「其实我们的节点类似一个 skill，我们学习成熟的 skill 内容，不怕提示词太多，我们可以设计模式不同模式注入的提示词，你更新一下最新的 superpowers，看看最新的 superpowers 是有什么变化，这个可以立项」
>
> 「我们要通过 hook 的方式、user_answer_question、workflow 等功能把 14 个 skill 串联起来，这个需求内容，我们还有通过需求难度和拆分、实施的内容，做到提示词注入不同，尽量做到节省 token —— 这个需要一个好设计方式」
>
> 「每个节点有最少 2 个不同的提示词，一个多一个少，多的解决难问题，少的解决简单的，还可以根据立项类型不同，选择注入不同的提示词。例如 bug 要注入的提示词和需求要注入的提示词就是不一样。这个要好好设计，我们插件提示词那里也需要好好设计，设计一个提示词加载路由」

### 1.1 新旧 superpowers 对比（实测）

| 项 | 旧提交 b5576485 | 最新 main |
|----|-----------------|-----------|
| brainstorming 体量 | 10,598 字符 | **15,456 字符** |
| 结构 | 单一 9 项线性 checklist | **Three Paths 分级**（Spike / Bounded / Architectural）+ 按路径分支的 checklist + Red Flags 表 |
| 核心不变量 | HARD-GATE | 措辞升级：**the ceremony scales with the task; the approval gate never does**（仪式随任务伸缩，批准闸门永不伸缩） |
| 生态 | 10 个 skill | **14 个 skill**（新增 executing-plans / verification-before-completion / test-driven-development / systematic-debugging / requesting+receiving-code-review / using-git-worktrees / subagent-driven-development / dispatching-parallel-agents / finishing-a-development-branch / writing-skills / using-superpowers） |

### 1.2 现状缺口（逐条对照得出，非推测）

1. **无路径/难度分级**：今天只有 category 一条轴，靠 CATEGORY_FLOW_PROFILES 决定"启用哪些节点 / 生效哪些门 / 是否注入"。它能**跳过阶段**，但做不到"同一阶段按任务轻重注入不同仪式"。
2. **提示词是单份常量**：StagePromptSpec 里每阶段一份，没有"多/少"两档，也无法按立项类型分化（bug 与 feature 注入同一份）。
3. **清单是散文**：9 步没有落成可勾选任务，步骤被跳过没有任何提示——这是本窗口这两天反复踩的坑。
4. **无回退环**：设计未获认可怎么办、文档被要求改怎么办，文本里没写。
5. **无 YAGNI 纪律、无分节篇幅与要素规范**（superpowers 要求覆盖 architecture/components/data flow/error handling/testing 且篇幅按复杂度伸缩）。
6. **注入内容不可审计**：此前"给 agent 看的注入文本"长期残留 10 处旧工具名（13→9 收敛后），因为**没人看得见到底注入了什么**。
7. **14 个成熟 skill 未被系统吸收**：目前只在文本里零散提"superpowers 式"。
8. **上下文不可丢弃（跨窗口接手成本高）**：注入的提示词不含"上游各节点产出了什么、当前该干嘛"，接手方只能靠人转述或自己翻文档。用户 2026-09-17 的反问（能否弃上下文重开）恰好暴露这条缺口。

## 2. 目标与非目标

### 2.1 目标

- **G1 提示词加载路由**：用「节点 × 难度 × 立项类型」作为路由键，按**分级回退**解析出该注入哪一份文本；路由是唯一对外入口。
- **G2 每节点至少两档**：light（简单）/ heavy（难）；并支持按 category 分化（bug 与 feature 的提示词不同）。
- **G3 串成链**：每个节点的提示词末尾显式声明"下一步是哪个节点、用哪个工具交棒"，把 14 个 skill 要点按节点串起来（hook 注入 + 弹框交接 + workflow 骨架）。
- **G4 省 token**：编写不设限（库可以长），**注入受预算约束**（只注当前节点选中的片段；清单/闸门/红旗为保底不可裁；同片段不重复注入）。预算口径 = 注入字符数（token 的代理指标，确定性可测）。
- **G5 可审计**：每次注入记录 routeKey、命中层级、片段 id、字符数——回答"这次到底注入了什么"。
- **G7 节点级上下文隔离（同窗口遗弃式）**：节点切换时在**同一个窗口**里遗弃模型可见的上下文（会话 surface 整段替换），替换内容 = 下一节点的输入包，输入 100% 来自「路由提示词 + 文档 + 台账投影」。不派 subagent、不做压缩、不新开会话；事件日志保留可追溯。
- **G6 上下文可丢弃（断点自描述）**：任一节点被新窗口接手时，注入的提示词 + 落盘文档必须自足——接手方无需上一窗口的记忆即可续跑。判据：新窗口只看注入文本 + 需求文档，就能说出"当前节点、上游结论、下一步用哪个工具"。

### 2.2 非目标

- **N1** 不改状态机与 rollup 的推进规则（链的骨架维持现状）。
- **N2** 不改 category 的现有职责（启用哪些节点/哪些门）；难度是新维度，不替换 category。
- **N3** 不把主纪律交给模型自主 load（违背 REQ-31e11f 既定裁定"纪律必须确定性注入，不走 skill"）；skill 内容只作**素材**。
- **N4** 不追求 14 skill 与 7 节点的 1:1 映射（按**要点**映射）。
- **N5** 本期不实现 Visual Companion 的浏览器伴侣本体，只实现"独立成一弹的提议"这一交互约束。

## 3. 方案：提示词加载路由

### 3.1 §1 路由键与回退链（已确认）

路由键 = (stage, difficulty, category)。当前 6 个可注入节点（brainstorming/planning/decomposing/implementing/accepting/archived；draft 是入口态、不注入）× 2 难度 × 6 类型 = 72 组合，不逐一编写，用**分级回退**：

    ① (stage, difficulty, category)  精确命中
    ② (stage, difficulty, *)         该类型无专属 → 用难度档
    ③ (stage, *, category)           该难度无专属 → 用类型档
    ④ (stage, *, *)                  该节点兜底档
    ⑤ (*, *, *)                      全局兜底（只放"批准闸门不可伸缩"这类铁律）

**优先级：难度优先于类型**——难度决定仪式强度（要不要写 spec、要不要逐项确认），类型只做提示差异（bug 先查业务文档、refactor 先盘依赖）。
**难度两档**：light / heavy。**Spike 不进难度轴**：它是 category，其"不写 spec"的仪式由第 ③ 层（类型档）承担。

### 3.2 §2 库的组织形态（已确认）

**Markdown 作者态 + 构建期内联 + 门禁校验**：

    src/domain/prompt/
      index.ts                路由入口（唯一对外函数 resolveStagePrompt）
      router.ts               回退链 + 去重 + 预算裁剪 + 命中留痕
      budget.ts               注入预算与保底（清单/闸门/红旗永不被裁）；预算以**字符数**为口径，
                              它是 token 的代理指标（确定性、可测、与既有 LIMITS 口径一致）
      fragments/
        common/               全局铁律（批准闸门不可伸缩、清单纪律、红旗表）
        brainstorming/{light.md, heavy.md, bug.md, feature.md, …}
        planning/…  implementing/…  accepting/…
      generated/fragments.ts  构建期把 .md 内联成常量

理由：这批文本要长期人工打磨（人与 agent 都要读改），.md 比 TS 模板串好写数个量级；而"确定性注入"要求编译进产物，**不能运行时读盘**（本仓多次踩"读盘失败静默降级"）。故：md 写、构建内联、测试断言产物与源同步。

### 3.3 §3 留痕与四条门禁（已确认）

**留痕**：每次注入记录 routeKey / 命中层级(exact|②③④) / 片段 id 列表 / 字符数。

**门禁**：
1. **覆盖检查**：任意 (stage, difficulty) 都能解析出非空片段（不出现"无提示词"）。
2. **工具名一致性**：注入文本里的 reqboard_* ∈ 实际注册集合（已在 tests/stage-prompts.test.ts 建好，本需求接上）。
3. **预算上限**：单次注入 ≤ N 字符，超限即红（编写不限、注入有闸）。
4. **片段唯一性**：id 不重复；**无孤立片段**（写了没被任何路由命中 = 死提示词）。

### 3.4 §4 串联机制（已确认）

三条通道（全部用现有机制）：

| 通道 | 承担 | 现状 |
|------|------|------|
| hook 注入 | 当前节点的提示词：每回合 systemPrompt 组装（capture-section）+ 状态转移后（CaptureHook） | 已有；只需把取词换成 resolveStagePrompt({stage,difficulty,category}) |
| 弹框 | 交接点：节点出口门确认 + 下一步选择；"要不要可视化"这类提议单独成一弹 | 已有 |
| workflow | 链的骨架：节点推进 | 已有 |

**增量：把"链"写进文本**——每个节点提示词末尾固定一行：

    下一步：<next stage> —— 用 <tool> 交棒；未获批准不得进入（闸门永不伸缩）

并被门禁校验：**每个节点必须声明下一步**（漏了即红）。对齐 superpowers 的"brainstorming 之后只能调 writing-plans"。

**skill ↔ 节点要点映射（设计交付物）**：

| 节点 | 吸收哪些 skill 的要点 |
|------|----------------------|
| brainstorming | brainstorming（主体）+ using-superpowers（入口纪律：先分类宣布路径） |
| planning | writing-plans（计划四要素 + 提交前自查） |
| implementing | executing-plans + test-driven-development + subagent-driven-development + using-git-worktrees + dispatching-parallel-agents |
| accepting | verification-before-completion + requesting-code-review + receiving-code-review |
| 横切 | systematic-debugging（implementing/accepting 排障）、writing-skills（元：如何写提示词本身） |
| 归档/收尾 | finishing-a-development-branch（分支收尾与合并纪律） |

### 3.5 §5 分期（已确认）

| 期 | 内容 | 判定 |
|----|------|------|
| **P0 路由骨架** | prompt/ 目录 + router + budget + 覆盖/唯一/预算门禁；把现有 6 份提示词按新结构落位 | **零行为变更**：同一 (stage,category) 解析出的文本与今天逐字一致（既有测试全绿） |
| **P1 brainstorming 三路径** | light/heavy × category 分片；移植最新版：三路径分类与宣布、红旗表、按路径清单、YAGNI、分节篇幅伸缩、回退环 | 该节点解析结果按要求变化且门禁全绿 |
| **P2 其余主节点** | planning / implementing / accepting 各自的 light/heavy 与类型差异 | 逐节点验收 |
| **P3 串联与留痕** | "下一步"声明 + 注入留痕（routeKey/命中层级/片段 id/字符数）+ 独立成弹的可视化提议 | 注入可审计：能回答"这次到底注入了什么" |

**§3.6 落地顺序**：P0 先立提示词路由与门禁；**文档契约（INV-8 五字段）随 P0 一起加**——成本低，且是后续一切隔离执行的前提；真正切换成"节点边界同窗口遗弃上下文"放在 **P3**（必须先验证文档自足，否则会丢信息；隔离执行一旦上，文档漏写就没有对话历史兜底了）。

P0 是风险最低入口：只换取词方式、不改文本——延续"先立门禁再改内容"的既定纪律。

### 3.6 节点执行模型：上下文遗忘与文档承载

用户提出的设计判断（原话）：**「通过每个节点遗忘之前的内容，通过文档内容获取新的上下文内容，这样可以节省 token，所以文档内容和文档设计就很重要了」**。

**机制定位（2026-09-17 用户三轮澄清后定稿）：不是 subagent、不是压缩、也不新开窗口——是**同一个窗口**内把模型可见的上下文整段遗弃，只留下一个"节点输入包"作为新起点。**

| 机制 | 本 profile 状态 | 是否本需求机制 |
|------|----------------|---------------|
| **会话 surface 整段替换（同窗口、同 session id）** | **原生原语**：`SurfaceOp = append \| { op: replace, startSeq, endSeq }` | **是** |
| 新建会话（新 sessionId、同 preset） | 原生可编程（ctx.agents.create） | 否——用户："还是一个窗口" |
| compaction 压缩（历史 → 摘要，同会话继续） | 已启用 | 否——用户："不是压缩，是遗弃之前的上下文"（摘要仍留着过去） |
| 无种子 subagent / workflow 编排 | 已可用 / 引擎在、工具 disabled | 否 |

**可编程接口（读 dsh-session / dsh-agent 类型定义取证，2026-09-17）**：

    session.surface                    模型可见的唯一真相（"The ordered surface over this session's event log"）
    Session.append(type, data, opts)   消息类事件必须带 surfaceOp：
                                         { surfaceOp: 'append' }
                                       | { surfaceOp: { op: 'replace', startSeq, endSeq } }  ← 整段替换
    语义：append 一条 user/message 并声明 replace(0..N) → 模型可见面里 0..N 整段消失，只留新内容
    会话 id / 窗口 / 日志都不变；被替换的历史仍在事件日志里（回放可还原，审计不丢）
    这正是 compaction 后端用的同一个原语——区别只在"替换内容填什么"：
      压缩填的是过去摘要（LLM 生成）；本需求填的是**下一个节点的输入包**（我们从文档拼）

**结论**：要的形态（一个窗口 + 上下文真被遗弃 + 输入全来自文档）**能实现**，且比新建会话更省事——用 surface 整段替换，替换内容就是节点输入包。

**节点执行模型（本需求采用）**：

    节点 N 结算（在一个轮次边界、agent 空闲时）→
      ① 产物落盘（文档/台账）—— 先把状态写出去，再谈遗忘
      ② append 一条 user/message，surfaceOp = replace(起=**首个非 system 的 surface 节点**, 止=当前末尾)
         （t9 实测框架硬约束：surface 节点 0 是系统提示词，只能由 system/message 且恰为单节点改写；
          故"从第 0 条替换"被硬拒，合法形态正是 [系统段, 输入包]——与本节 ③ 的可观测结果一致）
         内容 = 节点 N+1 的输入包（§3.1-3.3 路由提示词 + 需求文档 + 台账投影）
      ③ 窗口没变、session id 没变；模型看到的只剩系统段 + 这份输入包
      ④ 人在同一个窗口里看到的就是"上一节点内容没了、换成下一节点的开工上下文"

**planning 必须验证的四件事（先记下，不许当成已解决）**：

1. **不变量合规（最大的技术风险）**：手写 replace 会不会违反对端配对/活动轮次/`sourceEventSeqs` 完整性等 surface 契约——compaction 那套有硬要求（两端必须 tool 调用/结果配对平衡，并导出了 `toolPairingBalancedBefore/After` 做边界检查）。planning 要在两条路里取舍并实测：**(A) 直接用 surface 原语**（替换内容完全可控＝节点输入包，但自己守不变量）vs **(B) 借 compaction seam 的 `compactRegion`**（框架守不变量，但替换内容由摘要后端生成，保不住"遗弃"语义）。
2. **时机**：必须落在轮次边界、agent 空闲（活动轮次 / 未配对工具调用会被拒）。节点结算点是否天然满足，实测。
3. **触达路径**：`session.surface` / `append` 是宿主侧会话对象的能力；本仓 reqboard 目前是页面插件（借 host 侧 capture hook 注入 systemPrompt）。要确认插件能否拿到 `Session`/`agent` 句柄；拿不到就按 §7 D-12 降级。
4. **人可见效果**：GUI 会话视图渲染的就是 surface——整段替换后，同一个窗口里历史会消失、只剩节点输入包。这是否符合预期（还是希望"历史仍在人可见、只是模型看不见"），需实测确认再定。

**由此推出的文档契约（本需求的关键交付）**：跨节点状态**只能**靠文档，所以每个节点产物必须自足——接手方单独打开它就够续跑。为此每个节点产物须含结构化头部：

| 字段 | 作用 |
|------|------|
| 当前节点 | 接手方知道自己在流水线哪一步 |
| 上游结论 | 上游节点已经决定了什么（不重复讨论） |
| 未决问题 | 尚待确认/待批准的开放项 |
| 下一步 | 用哪个工具交棒给哪个节点 |
| 证据指针 | 结论的依据在哪（文件/命令/工具回执） |

**成本收益**：token 从"随会话线性增长"变为"每节点常数 + 该节点所需文档片段"；代价是文档必须写全（可丢弃上下文的前提就是文档自足）。这正是用户说的"文档内容和文档设计就很重要"。

## 4. 不变量清单（验收基准）

- **INV-1 单一入口**：取词只能经 resolveStagePrompt；不得再有 STAGE_PROMPTS[stage] 直取（机械检查：注入点只有一处调用）。
- **INV-2 回退完备**：任意 (stage, difficulty, category) 都解析出非空片段；⑤ 全局兜底必须存在且只含铁律。
- **INV-3 预算保底**：清单/闸门/红旗三类片段**永不被预算裁剪**（裁剪只作用于次要片段，且按显式优先级）。
- **INV-4 链声明**：每个节点提示词含"下一步"声明，且其 next 必须是状态机允许的后继。
- **INV-5 工具名一致**：注入文本里的 reqboard_* ∈ 注册集合（沿用已建门禁）。
- **INV-6 可审计**：每次注入产出可查记录（routeKey/命中层级/片段 id/字符数）。
- **INV-9 节点输入包自足**：投递给新会话的输入包只含「路由提示词 + 需求文档 + 台账投影」，不得夹带前序对话摘录（否则"遗弃"名不副实且 token 又涨回来）；且 INV-8 五字段齐全。
- **INV-8 节点产物自足**：任一节点产物含结构化头部五字段（当前节点/上游结论/未决问题/下一步/证据指针）；缺任一字段即红（机械检查）。这是 G6/G7 成立的前提。
- **INV-7 零行为变更（仅 P0）**：P0 完成后，既有 stage-prompts 测试断言的文本解析结果逐字不变。

## 5. 验收标准

| # | 标准 | 判定方式 |
|---|------|---------|
| A1 | 路由与门禁测试全绿：覆盖检查、预算上限、片段唯一、无孤立片段、链声明、工具名一致 | npx vitest run（包内） |
| A2 | P0 零行为变更：既有阶段提示词解析结果与改造前逐字一致 | 既有 tests/stage-prompts.test.ts 全绿（不改断言） |
| A3 | brainstorming 按路径分化：light/heavy/bug/feature 解析出不同文本，且 heavy 含三路径分类、红旗表、YAGNI、回退环 | 断言各档关键要素存在 + 相互不同 |
| A4 | 预算生效：构造超预算场景 → 次要片段被裁、保底三类不被裁 | 单测断言裁剪前后差异 |
| A5 | 留痕可查：注入记录含 routeKey/命中层级/片段 id/字符数 | 单测断言记录结构 |
| A7 | 节点级上下文隔离可验证：模拟"只给注入提示词 + 需求文档"的全新上下文，能正确说出当前节点、上游结论与下一步 | 构造最小输入包走一遍（人工/半自动），对照 INV-8 五字段 |
| A6 | 类型检查与消息卫生门禁不退化 | npx tsc --noEmit -p tsconfig.json 0 错误；tests/message-hygiene.test.ts 绿 |

## 6. 风险与对策

| 风险 | 对策 |
|------|------|
| 分片爆炸（84 组合）| 回退链 + 门禁"无孤立片段"倒逼只写真正需要的档；先只做 brainstorming |
| 注入变长导致 token 反升 | 预算上限门禁 + 留痕记录字符数（可对比改造前后） |
| 构建期内联与源文件不同步 | 测试断言 generated 产物与 .md 源一致（改了 md 没重建即红） |
| 难度判定主观、agent 自行其是 | 难度由 agent 宣布、**用户可推翻**；留痕可见；单向升级（发现复杂 → 升 heavy，不许降） |
| 遗弃上下文后缺信息 → 返工 | 产物**先落盘再遗弃**（§3.6 步骤 ① 在 ② 之前）+ 节点输入包自足（INV-8/INV-9）+ 日志保留可追溯；切换前用 A7 实测"只给文档能否续跑" |
| 手写 surface replace 违反不变量（配对/活动轮次） | §3.6 末第 1、2 条列为 planning 必验项；优先复用 dsh-compaction 导出的边界检查工具，必要时退回 compactRegion |
| 与既有 CATEGORY_FLOW_PROFILES 职责混淆 | 明确分工：profiles 管"启用哪些节点/门"，router 管"注入什么文本"，共用 category 但不重叠 |

## 7. 本阶段决策记录

| # | 决策 | 依据 |
|---|------|------|
| D-1 | 路径不落数据轴：三路径的仪式**全部写进插件提示词**，由 agent 现场分类并宣布，用户可推翻 | 用户 2026-09-17 弹框答复："借鉴 superpowers 的内容，提示词写到插件里" |
| D-2 | 采用"提示词库 + 选择器 + 渐进披露"（方案 B），并吸收按需取全文 | 用户答复强调"串联 + 差异化 + 省 token，需要一个好设计方式"；纯确定性全量注入会烧 token，纯 skill 自主 load 违背既定裁定 |
| D-3 | 每节点至少 light/heavy 两档，且支持按 category 分化 | 用户原话："每个节点有最少 2 个不同的提示词，一个多一个少……还可以根据立项类型不同，选择注入不同的提示词" |
| D-4 | §1 路由键与回退链（难度优先于类型；Spike 走类型档） | 用户弹框确认 §1-§3 |
| D-5 | §2 库形态 = md 作者态 + 构建期内联 + 门禁校验 | 用户弹框确认 §1-§3 |
| D-6 | §3 留痕 + 四条门禁 | 用户弹框确认 §1-§3 |
| D-7 | §4 三条串联通道 + "下一步"显式声明 + skill↔节点要点映射 | 用户弹框确认 §4-§5 |
| D-8 | §5 P0-P3 分期，P0 零行为变更先立路由与门禁 | 用户弹框确认 §4-§5 |
| D-10 | 节点隔离 = **同窗口 surface 整段替换**：append 节点输入包并 `surfaceOp: replace(0..N)`（G7 + §3.6） | 用户 2026-09-17 四轮澄清：①"通过每个节点遗忘之前的内容，通过文档内容获取新的上下文内容，这样可以节省 token" ②"不是 subagent 是 mainagent 的上下文…节点和节点之前上下文隔离开" ③"不是压缩，是遗弃之前的上下文" ④"还是一个窗口，能实现吗" → 定稿为同窗口 surface 替换 |
| D-12 | 降级链：① 能触达 Session/surface → 插件做整段替换（目标形态）② 不能 → 节点边界**弹框请人开新窗口并粘贴节点输入包**（人可操作的等价路径）③ 兜底：同窗口只做"文档自足 + 重注入"（不遗弃，正确性不丢，但 token 不省） | surface 替换涉及不变量合规/时机/触达路径三个未验证项（§3.6 末）；先别把可行性押在未验证的接口上，但设计上要能逐级降级 |
| D-11 | 每个节点产物必须带结构化头部五字段（INV-8） | 同上——上下文可丢弃的前提是文档自足；缺字段则接手方必须回问人，省下的 token 又还回去 |
| D-9 | 把"上下文可丢弃"升为设计目标 G6 | 用户 2026-09-17 提问："因为我们是节点触发还写文档，我们可以把之前的上下文遗弃掉，重新开始一个新的上下文，这样可以吗" |

| D-13 | **节点即选择器，不需要 skill 匹配**：内容来源改为 **vendor superpowers 原文**（heavy=原文，light=自写精简）；"渐进式披露"落在注入时机（到哪个节点才给哪份） | 用户 2026-09-17："难度的就是完全 superpowers skill 的内容还直接渐进式披露，但是我们是节点推进的相当于选中，不需要匹配了，就是加载具体内容是披露的方式" |
| D-14 | vendor 来源锁定：obra/superpowers **v6.3.0 / commit b36e082（2026-08-12）**，MIT；仓库内保留 ATTRIBUTION 与版本号 | 实测取证：本地克隆 HEAD=6fd4507 是旧版（brainstorming 164 行 10,634 字节、**不含 Three Paths**）；最新 main=b36e082 含 "brainstorming three-path router"，brainstorming=15,456 字节 |

**vendor 体量事实（2026-09-17 实测，git show origin/main 计数）**：14 个 skill 合计约 14.4 万字节；单份最大 subagent-driven-development 32,339 字节、writing-skills 26,360、brainstorming 15,456、systematic-debugging 9,465、test-driven-development 9,015。**结论：heavy 不能把同一节点的全部相关 skill 一起注入**（implementing 相关五份合计约 5.6 万字节≈2 万 token），必须区分"主 skill 全文"与"按需片段"。

| D-15 | 替换区间 = **首个非 system 节点 → 末尾**（保留系统段）；**路线 B 不构成出路** | t9 实测：`surface replace: node 0 holds the system prompt and may be rewritten only by a system/message over exactly that node`（dsh-session surface.js:338）；compactRegion 最终走同一 append-replace 契约，同样被拒 |
| D-16 | 框架耦合全部下沉 adapters：application 层禁 import @deepseek-ai/*（既有 layer-boundary 门禁）；dsh-compaction 在本包依赖树不可解析（ERR_MODULE_NOT_FOUND）且计划禁新增依赖 → 边界配对检查按同算法在 adapters 内等价移植并注明来源 | 同上实测 |
| D-17 | t10 的隔离动作必须移出 session 事件派发 | t9 实测：监听器内同步 append 被拒（"session append cannot reenter while another append is being published"） |

## 8. 下一步

## 9. 确认记录（抗上下文丢失）

本节的作用：**让本需求可以换窗口接手**。凡经用户确认的内容都记在这里，接手方只看文档即可续跑。

| 时点 | 确认方式 | 确认内容 |
|------|---------|---------|
| 2026-09-17 | 弹框（ask_user_question） | §1 路由键与回退链（难度优先于类型；Spike 走类型档） |
| 2026-09-17 | 弹框 | §2 库形态 = md 作者态 + 构建期内联 + 门禁校验 |
| 2026-09-17 | 弹框 | §3 注入留痕 + 四条门禁 |
| 2026-09-17 | 弹框 | §4 三条串联通道 + "下一步"声明 + skill↔节点要点映射 |
| 2026-09-17 | 弹框 | §5 分期 P0-P3（P0 零行为变更先立路由与门禁） |
| 2026-09-17 | 弹框 | 本需求按 Architectural 路径走完整流程 |

**当前断点**：brainstorming 已完成、requirement.md 已登记（submitted）；下一步 = planning（写实施计划并请人批准）。

**接手方法（跨窗口）**：本需求的绑定锚点是立项窗口（sourceSessionId）。新窗口默认不是绑定窗口，调 reqboard_move/submit/accept_sheet 会被拒（REQBOARD_NOT_BOUND_TO_WINDOW）。设计上的接手路径 = 新窗口触发立项捕获生成建议卡（suggestedAction=bind_req）→ **人在看板点「绑定需求」** → 绑定后即可推进。该路径尚未端到端实测，接手时以实际返回为准；若被拒，可在看板直接对需求操作。

## 10. 下一步

进入 planning（技术设计）：产出 design/architecture.md（路由与分片元数据契约）、design/fragments.md（分片清单与映射表）、design/test-cases.md（六条不变量 → 用例矩阵）、design/migration.md（P0 零行为变更的等价性证明方式），然后提交实施计划请人批准。
