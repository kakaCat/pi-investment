# brainstorming 节点提示词 vs superpowers brainstorming SKILL.md —— 逐要素对照

> 产出：REQ-422af1 · t7 前置对照（只读比对，不改代码）
> 产出窗口：w-492d538d（本对照窗口）｜需求属主窗口：w-41e7e4cd
> 对标物版本：**obra/superpowers · origin/main · commit b36e0829c6d0140e93cfef2ca599b1b07d4a7797 · tag v6.3.0 · MIT**
> 结论纪律：每个判断带行号 + 原文片段；缺就写「完全缺失」，不用「部分覆盖」含混。

## 0. 基准与可核验性

| 项 | 内容 |
|----|------|
| 输入 A（我方） | /Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/src/domain/stage/StagePromptSpec.ts，只看 brainstorming 段：**L34-L52**（正文 L35-L51，共 9 条清单 + 标题行）。同文件另有 planning L54-73、decomposing L75-91、implementing L93-112、accepting L114-130、archived L132-153，本对照只在节点归属需要时引用。 |
| 输入 B（superpowers） | /tmp/sp-brainstorming-latest.md = origin/main:skills/brainstorming/SKILL.md，**250 行 / 15,456 字节**（第 1 次核对：origin/main 该文件 wc -c 同为 15456，一致）。 |
| 章节计数 | grep '^#' 得 **9 个 markdown 标题**：L6 标题、L22 Three Paths、L54 Anti-Pattern、L63 Red Flags、L75 Checklist、L105 Process Flow、L156 The Process、L202 After the Design、L233 Visual Companion。另有 **15 处粗体子节**（L80 Spike / L87 Bounded / L94 Architectural / L149 Terminal states / L164 Understanding the idea / L174 Exploring approaches / L181 Presenting the design / L189 Design for isolation and clarity / L196 Working in existing codebases / L204 Documentation / L211 Spec Self-Review / L221 User Review Gate / L228 Implementation / L237 Offering the companion / L242 Per-question decision）。 |
| 本表行数 | **44 行 ≥ 9 个标题**，且逐行覆盖上述 15 处粗体子节与 L14 HARD-GATE、L10-12 开场句（非标题但必查）。 |
| 引用口径 | 我方行号一律指 StagePromptSpec.ts；SP 行号一律指 /tmp/sp-brainstorming-latest.md。原文片段用「」包裹，省略处以 … 标记。 |

### 我方 brainstorming 段全文锚点（逐行读完整，L34-L52）

- L34-L35：分片键 brainstorming + 标题行「## 【阶段纪律 · 需求分析】（REQ-31e11f stage-prompts；REQ-2e9473 t18：superpowers 式方法论）」
- L37：「当前需求处于 brainstorming（需求分析/方案共创）阶段。**按检查表逐项执行**：」
- L39 第1条 探索项目上下文｜L40 第2条 范围评估先行｜L41-42 第3条 澄清提问（一次一个问题）｜L43 第4条 2-3 个方案对比｜L44 第5条 分节呈现设计｜L45-46 第6条 写需求文档｜L47 第7条 文档自查｜L48-49 第8条 用户审阅文档｜L50-51 第9条 HARD-GATE

---

## 1. 逐要素对照表（44 行）

| # | 要素 | superpowers（有/无 + 行号 + 原文） | 我方（有/无 + 行号 + 原文） | 差距性质 |
|---|------|-----------------------------------|------------------------------|----------|
| 1 | 文件头/触发语义（frontmatter） | 有 L1-L4：「name: brainstorming」「description: \"You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior.\"」 | 无 frontmatter；L34-L35 仅分片键 + 标题行，注入由 capture.ts / CaptureHook.ts 确定性触发（StagePromptSpec.ts L4-L6 注释：「skill 是模型自主调用，纪律必须**确定性注入**」） | 我方更强（确定性注入 > 模型自主 load） |
| 2 | H1 标题 + 一句定位 | 有 L6-L8：「# Brainstorming Ideas Into Designs」「Help turn ideas into fully formed designs and specs through natural collaborative dialogue.」 | 有 L35、L37：标题行 + 「当前需求处于 brainstorming（需求分析/方案共创）阶段」 | 等价 |
| 3 | 开场：先分类再走路径 | 有 L10-L12：「Start by classifying how much process the request needs, then work through your path: understand the context, refine the idea, present a design, and get your human partner's approval.」 | 无（L37 只有「按检查表逐项执行」，无条件分支） | **完全缺失** |
| 4 | HARD-GATE 批准闸门 | 有 L14-L20：「<HARD-GATE> Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have told your human partner what you intend and they have approved it.」 | 有 L50-L51 第9条：「**HARD-GATE**：文档未经确认不得进入技术设计/实现动作……（代码级也会拦：artifact_not_confirmed）」 | 等价（我方另有代码级拦截） |
| 5 | 闸门不随仪式伸缩 | 有 L18-L19：「This applies to EVERY task on EVERY path below — the ceremony scales with the task; the approval gate never does.」 | 有 L51：「『太简单不用走流程』是反模式，文档可以短但不能跳」 | 等价 |
| 6 | 三路径分类 + 开工前宣布 + 人可否决 | 有 L24-L28：「Before your first question, classify the request and say the classification out loud — 『this looks bounded, so I'll present a short design here rather than write a spec』 — so your human partner can override it」 | 无 | **完全缺失** |
| 7 | Spike 路径定义 | 有 L29-L34：「**Spike** — a feasibility question (『can we...』, 『is it possible...』, 『quick and dirty is fine』) whose output is an answer, not code you keep. … No design doc, no spec file. … anything you built stays labeled throwaway.」 | 无 | **完全缺失**（且其中「无 spec」条款与本仓产物闸门冲突 → 见 §2④-6） |
| 8 | Bounded 路径定义 | 有 L35-L44：「**Bounded** — a well-scoped change to code that already exists in this repo … bounded means the flow you are changing is already here to read. … present a short design IN CHAT … and STOP. … No spec file, no implementation plan document.」 | 无 | **完全缺失**（同上，产物豁免冲突） |
| 9 | Architectural 路径定义 | 有 L45-L48：「**Architectural** — new projects, new subsystems, changes that restructure how components fit together … Follow the full process: questions, approaches, sectioned design, written spec, then the writing-plans skill.」 | 有 L37「**按检查表逐项执行**」+ L39-L51 九条，等价于 architectural 一条路径但**未命名、无分类、无替代路径** | 更弱（只覆盖三条中的一条，且不自知是"最重那条"） |
| 10 | 拿不准取更重 + 单向棘轮 | 有 L50-L52：「When in doubt between two paths, take the heavier one. The ratchet is one-way: hidden complexity discovered mid-task upgrades the path — stop, say so, and step up. Nothing downgrades mid-task.」 | 无 | **完全缺失** |
| 11 | Anti-Pattern：「太简单不用批准」 | 有 L54-L61：「Every path ends with your human partner approving your intent before implementation. A todo list, a single-function utility, a config change — the design may be two sentences in chat, but you MUST present it and get approval. … What scales with simplicity is the artifact, never the approval.」 | 有 L50-L51（一句）：「『太简单不用走流程』是反模式，文档可以短但不能跳」 | 更弱（核心句等价，缺 SP 的三例展开：todo/单函数/配置改动） |
| 12 | Red Flags 表（7 行） | 有 L63-L73：如「『This is too simple to need a design』 → Simple means a short design, not no design.」「『I'll call it bounded and skip the spec』 → Reaching for a label to skip work IS the doubt」「『It's bounded and the design is obvious — I'll start while they read it』 → The gate is the approval, not the design's length」等 7 条 | 无 | **完全缺失** |
| 13 | Checklist 前言（先分类/宣布/逐项按序完成） | 有 L77-L78：「Classify first, announce the path, then create a task for each item on your path and complete them in order.」 | 有 L37：「**按检查表逐项执行**」 | 更弱（缺"先分类/宣布路径/逐项建 task"；且"建 task"语义在我方需改写，见 §2②-2） |
| 14 | Checklist · Spike 分支清单（5 项） | 有 L80-L85：「1. Explore project context … 3. Get approval — a nod is enough … 5. Report findings — a recommendation; label anything built as throwaway」 | 无 | **完全缺失** |
| 15 | Checklist · Bounded 分支清单（5 项） | 有 L87-L92：「3. Present short design in chat — approach, files touched, testing」「4. Get approval — STOP and wait for an explicit yes; presenting the design and starting in the same breath is skipping the gate」「5. Implement … no plan document」 | 无 | **完全缺失** |
| 16 | Checklist · Architectural 分支清单（9 项） | 有 L94-L103：Explore project context／Offer the visual companion just-in-time／Ask clarifying questions／Propose 2-3 approaches／Present design／Write design doc／Spec self-review／User reviews written spec／Transition to implementation | 有 L39-L51 九条（编号 1-9），同为 9 步骨架 | 等价（步骤数 1:1；第 2、9 位内容不同：SP=视觉伴侣/交棒 skill，我方=范围评估/HARD-GATE） |
| 17 | Arch#2 视觉伴侣及时提议（just-in-time） | 有 L96：「**Offer the visual companion just-in-time** — NOT upfront. … offer it then (its own message); on approval its browser tab opens for you. If no visual question ever arises, never offer it.」 | 无（L40 第2条位置被"范围评估先行"占据） | **完全缺失** |
| 18 | Arch#3 澄清提问 | 有 L97：「**Ask clarifying questions** — one at a time, understand purpose/constraints/success criteria」 | 有 L41-L42 第3条 | 等价 |
| 19 | Arch#4 提出 2-3 个方案 | 有 L98：「**Propose 2-3 approaches** — with trade-offs and your recommendation」 | 有 L43 第4条 | 等价 |
| 20 | Arch#5 分节呈现设计并逐节确认 | 有 L99：「**Present design** — in sections scaled to their complexity, get user approval after each section」 | 有 L44 第5条：「需求文档分节写，每节先请用户确认再写下一节（禁止一次性全文）」 | 等价 |
| 21 | Arch#6 设计文档落盘位置与登记 | 有 L100／L206-L207：「**Write design doc** — save to docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md」 | 有 L45-L46 第6条：「产出 requirement.md（docs/requirements/REQ-xxxxxx/，头部带 REQ id）；过程产物（原型 html 等）落进需求目录即自动登记（W4）」 | **我方独有**（REQ 账本 + 自动登记，SP 无对应机制） |
| 22 | Arch#6 设计文档 git commit | 有 L100／L209：「and commit」「Commit the design document to git」 | 无（L45-L49 无任何 git 动作；提交由仓库合流流程管） | **完全缺失**（判定为"不采用"，见 §2④-5） |
| 23 | Arch#7 的展开节：Spec Self-Review 四项 | 有 L101／L211-L219：Placeholder scan（TBD/TODO/vague）／Internal consistency／Scope check／Ambiguity check；「Fix any issues inline. No need to re-review — just fix and move on.」 | 有 L47 第7条：「占位符/矛盾/模糊/范围蔓延逐项过完再提交」 | 等价（4/4 一一对应，我方是压缩版） |
| 24 | Arch#8 的展开节：User Review Gate | 有 L102／L221-L226：「ask the user to review the written spec before proceeding」+ 引用文案「Spec written and committed to <path>. Please review it…」+「If they request changes, make them and re-run the spec review loop. Only proceed once the user approves.」 | 有 L48-L49 第8条：「调 reqboard_ask_confirm（target=artifact, kind=requirement）弹框请人确认——肯定答复自动落章并推进到 planning（先 reqboard_submit(kind=requirement) 登记产物）」 | 我方更强（工具化闸门 + 自动推进）；但缺 SP L226 的"改后重跑自查环" |
| 25 | Arch#9 终态交棒 | 有 L103：「**Transition to implementation** — invoke writing-plans skill to create implementation plan」 | 有 L48-L49（推进到 planning） | 等价（语义一致，机制不同） |
| 26 | Process Flow DOT 状态图 | 有 L105-L147：digraph，含「\"Human approves?\"」「\"Invoke writing-plans skill\"」「\"Hidden complexity? Upgrade path\"」及 19 条边 | 无 | **完全缺失**（判定为"不采用"，见 §2④-7） |
| 27 | Terminal states are path-bound | 有 L149-L154：「Architectural: the ONLY skill you invoke after brainstorming is writing-plans — never frontend-design, mcp-builder, or any other implementation skill. Bounded: … Spike: the terminal state is a reported recommendation.」 | 有 L48-L49（只写"推进到 planning"），**无"只能/不得"约束、无禁用其他 skill 的措辞** | 更弱（缺终态唯一性约束） |
| 28 | The Process 前言（哪些小节适用于哪条路径） | 有 L158-L162：「The subsections below serve the bounded and architectural paths … Sections from **Exploring approaches** onward are architectural-path depth」 | 无（我方无路径概念，故无适用范围说明） | **完全缺失** |
| 29 | Understanding the idea：先看项目现状 | 有 L166：「Check out the current project state first (files, docs, recent commits)」 | 有 L39 第1条：「先读相关文件/文档/最近变更，建立事实基础再开口问」 | 等价 |
| 30 | Understanding the idea：范围评估/拆子项目 | 有 L167-L168：「if the request describes multiple independent subsystems … flag this immediately. Don't spend questions refining details of a project that needs to be decomposed first.」「help the user decompose into sub-projects … Each sub-project gets its own spec → plan → implementation cycle.」 | 有 L40 第2条：「请求涉及多个独立子系统时，先帮用户拆子项目——不要先扎进细节」 | 更弱（缺"子项目各自走自己的 spec→plan→实施循环"在本仓的落点＝各自立项） |
| 31 | Understanding the idea：一次一个问题/多选优先/目的约束成功标准 | 有 L169-L172：「ask questions one at a time」「Prefer multiple choice questions when possible」「Only one question per message」「Focus on understanding: purpose, constraints, success criteria」 | 有 L41-L42 第3条：「用弹框逐个问关键问题，理解目的/约束/成功标准/边界情况；禁止一口气抛出全套方案」 | 等价（我方弹框天然承载多选） |
| 32 | Exploring approaches：方案对比方式 | 有 L174-L178：「Propose 2-3 different approaches with trade-offs」「Present options conversationally with your recommendation and reasoning」「Lead with your recommended option and explain why」 | 有 L43 第4条：「给选项时必须 2-3 个 + 优缺点/成本/风险，标注推荐项与理由」 | 等价 |
| 33 | Exploring approaches：YAGNI ruthlessly | 有 L179：「YAGNI ruthlessly - remove unnecessary features from every approach and design」 | 无 | **完全缺失** |
| 34 | Presenting the design：篇幅随复杂度伸缩 | 有 L183-L185：「Scale each section to its complexity: a few sentences if straightforward, up to 200-300 words if nuanced」「Ask after each section whether it looks right so far」 | 有 L44 第5条（分节 + 逐节确认），**无篇幅伸缩口径** | 更弱（缺"几句话 ~ 200-300 词"的伸缩标尺，恰与本仓 light/heavy 两档天然契合） |
| 35 | Presenting the design：设计覆盖面 | 有 L186：「Cover: architecture, components, data flow, error handling, testing」 | brainstorming 段内无；相近内容在我方 planning 段 L59-L64（数据层/选型/代码规范/UI/测试用例） | **完全缺失**（brainstorming 段内；属节点归属差异，需 t7 裁定是否并入 heavy 附加片段） |
| 36 | Design for isolation and clarity | 有 L189-L194：「Break the system into smaller units that each have one clear purpose, communicate through well-defined interfaces … what does it do, how do you use it, and what does it depend on?」「When a file grows large, that's often a signal that it's doing too much.」 | 无 | **完全缺失** |
| 37 | Working in existing codebases | 有 L196-L200：「Explore the current structure before proposing changes. Follow existing patterns.」「include targeted improvements as part of the design」「Don't propose unrelated refactoring.」 | 无（L40 的"范围评估"不涉及现有代码模式/顺手改/禁无关重构） | **完全缺失** |
| 38 | After the Design：Documentation 节（含 elements-of-style skill 引用） | 有 L204-L209：「Use elements-of-style:writing-clearly-and-concisely skill if available」+ 落盘 + commit | 有 L45-L46 + L48（reqboard_submit 登记） | 等价（落盘）；其中 elements-of-style 引用我方无 → 归"不采用"（§2④-3） |
| 39 | Visual Companion：定位（browser-based，tool not mode） | 有 L233-L235：「A browser-based companion for showing mockups, diagrams, and visual options during brainstorming. Available as a tool — not a mode.」 | 无 | **完全缺失**（本体判定"不采用"，§2④-1） |
| 40 | Visual Companion：及时提议 + 接受/拒绝处理 | 有 L237-L240：L238 提议文案「This next part might be easier if I show you … Want me to? I'll open it for you.」；L240「If they accept, start the server with --open so their browser opens to the first screen automatically. If they decline, continue text-only and don't offer again unless they raise it.」 | 无 | **完全缺失**（服务端本体不采用；"提议"交互保留，§2②-6） |
| 41 | Visual Companion：提议必须单独成一条消息 | 有 L240：「**This offer MUST be its own message.** Only the offer — no clarifying question, summary, or other content.」 | 无 | **完全缺失**（本需求明确要保留的一条交互约束 → §2②-6） |
| 42 | Visual Companion：per-question decision（browser vs terminal） | 有 L242-L247：「decide FOR EACH QUESTION whether to use the browser or the terminal. The test: **would the user understand this better by seeing it than reading it?**」「A question about a UI topic is not automatically a visual question.」 | 无 | **完全缺失**（浏览器分叉不采用；等价物＝按需单独弹框） |
| 43 | Visual Companion：详细指南引用 | 有 L249-L250：「If they agree to the companion, read the detailed guide before proceeding: skills/brainstorming/visual-companion.md」 | 无 | **完全缺失**（不采用，§2④-1） |
| 44 | After the Design：Implementation 节 | 有 L228-L231：「Invoke the writing-plans skill to create a detailed implementation plan」「Do NOT invoke any other skill. writing-plans is the next step.」 | 有 L48-L49（推进到 planning 节点） | 等价（机制不同：skill 调用 → 状态机 + 工具交棒） |

### 分类小结（44 行）

| 差距性质 | 行数 | 行号 |
|----------|------|------|
| 等价 | 14 | 2, 4, 5, 16, 18, 19, 20, 23, 25, 29, 31, 32, 38, 44 |
| 我方更强 | 2 | 1, 24 |
| 我方独有 | 1 | 21 |
| 更弱 | 6 | 9, 11, 13, 27, 30, 34 |
| **完全缺失** | **21** | 3, 6, 7, 8, 10, 12, 14, 15, 17, 22, 26, 28, 33, 35, 36, 37, 39, 40, 41, 42, 43 |
| 合计 | 44 | — |

---

## 2. 差距分类结论（四类）

### ① 直接 vendor：superpowers 原文照搬即可（6 条）

定义：原文可直接落入 heavy 分片，且不需要改写成我方节点语境（我方 0 覆盖，或仅有等价短句、替换即完成）。

| # | 条目 | SP 行号 | 我方覆盖 | 说明 |
|---|------|---------|----------|------|
| ①-1 | Three Paths 分类框架（含三路径定义、开工宣布、人可否决、单向棘轮） | L22-L52 | 0 | 表行 6/7/8/9/10 全部为「完全缺失/更弱」；框架本身跨仓通用，无需写我方上下文。**例外**：其中 Spike/Bounded 的"无 spec/无 plan 文档"条款不适用（→ ④-6，由附加片段显式否掉）。 |
| ①-2 | Red Flags 表（7 行） | L63-L73 | 0 | 表格式内容，逐字可用；语言与措辞不涉及本仓机制。 |
| ①-3 | Checklist · Spike 分支清单（5 项） | L80-L85 | 0 | 行为纪律（探索→呈探针→获批→以最省成本验证→报告结论）通用；仅第 5 项"throwaway"标注与产物闸门的冲突需附加片段兜底。 |
| ①-4 | The Process 的通用工程子节：Understanding the idea／Exploring approaches（含 YAGNI）／Presenting the design（含篇幅伸缩）／Design for isolation and clarity／Working in existing codebases | L164-L200 | 部分要点版（L39/L40/L41-42/L43/L44） | 表行 29/30/31/32 我方有要点版但**原文更详尽**（YAGNI、篇幅标尺、isolation、existing codebases 四项我方 0 覆盖，行 33/34/35/36/37）。vendor 后用原文，我方要点版不必保留重复内容。 |
| ①-5 | Spec Self-Review 四步 | L211-L219 | 有压缩版 L47 | **边界项**：按"我方没有对应内容"的严判据该项应落 ②，但它的处置动作是"vendor 后逐字替换我方 L47 单行、零改写"，故归 ①。 |
| ①-6 | Anti-Pattern 段 | L54-L61 | 有单行 L50-L51 | **边界项**（同上）：核心一致，vendor 后可覆盖/展开我方单行，零改写。 |

### ② 移植改写：内容可用，必须改写成我方节点语境（7 条）

| # | 条目 | SP 行号 | 改写要求 |
|---|------|---------|----------|
| ②-1 | HARD-GATE 措辞 | L14-L20 | "implementation skill / implementation action" → 「进入下一节点（planning/decomposing/implementing）或任何写代码/落库任务」；"human partner" → 「用户/需求负责人」。我方 L50-L51 已是该改写的成品，改写点落在附加片段与原文的映射说明（不改 vendor 原文，保逐字一致）。 |
| ②-2 | Checklist 前言「create a task for each item」 | L77-L78 | 本仓的 task = reqboard 任务卡，属于 **decomposing** 节点（W7 边界）。brainstorming 阶段若照原文理解会去建任务卡 → 改写为「节点内可勾选清单（注入文本自查）」。 |
| ②-3 | 设计文档落盘路径 | L100、L206-L207 | "docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md" → 「docs/requirements/REQ-xxxxxx/requirement.md（头部带 REQ id）」+ reqboard_submit(kind=requirement) 登记。 |
| ②-4 | User Review Gate 文案与回退环 | L221-L226 | 引用文案改为 reqboard_ask_confirm(target=artifact, kind=requirement) 的弹框问题；保留"人要求改 → 改完重跑 Spec Self-Review → 再请审"的回退环（我方 L48-L49 缺此环）。 |
| ②-5 | 终态交棒与终态唯一性 | L103、L149-L154、L228-L231 | "invoke writing-plans skill" → 「下一步：planning —— 调 reqboard_ask_confirm 交棒」；"never frontend-design / mcp-builder / any other implementation skill" → 「本仓只允许交棒给 planning 节点，不得直接跳到拆分/实施」（补我方差行 27 的终态约束）。 |
| ②-6 | Visual Companion："提议必须单独成一条消息" + per-question 分流 | L238、L240、L242-L247 | 去掉 server/--open/浏览器；移植为「如需可视化，用**独立一次弹框**提议，只含提议本身、不带其他内容」+「按问题逐个判断是否值得可视化（看图比读字更清楚才用）」。 |
| ②-7 | 逐节确认与"STOP and wait" | L91、L185 | "presenting the design and starting in the same breath is skipping the gate" 与本仓闸门语义一致，改写为我方弹框/确认动作（reqboard_ask_confirm 或 ask_user_question）。 |

### ③ 我方独有必须保留（7 条）

| # | 条目 | 位置 | 保留理由 |
|---|------|------|----------|
| ③-1 | reqboard 工具交棒链（reqboard_submit / reqboard_ask_confirm / reqboard_move / reqboard_status / reqboard_decompose / reqboard_task_move / reqboard_task_report） | L48-L49；planning L70-L72；decomposing L85-L88 | superpowers 用"skill 调用"表达交棒，本仓用工具 + 状态机，两者不可互换。 |
| ③-2 | 弹框确认机制（ask_user_question 逐问 + reqboard_ask_confirm 闸门） | L41、L48；implementing L110-L111 | 弹框是本仓唯一"请人拍板"通道；SP 的"问一句/等回复"在本仓要落到弹框。 |
| ③-3 | 需求 id 与目录账本（docs/requirements/REQ-xxxxxx/、头部带 REQ id、过程产物落目录即自动登记 W4） | L45-L46 | SP 的 specs 目录无 id 账本；REQ id 是状态机、产物门禁、看板的共同主键。 |
| ③-4 | 状态机闸门与代码级拦截 | L48-L51（artifact_not_confirmed） | SP 只有模型自律的 HARD-GATE；我方有代码级兜底，是更强的防线（表行 4/24 判"等价/我方更强"的依据）。 |
| ③-5 | 「下一步：<next stage> —— 用 <tool> 交棒」固定尾行 | design/fragments.md L119 | 让"交棒"成为可机检的固定格式；SP 无此约定。 |
| ③-6 | light/heavy 难度两档 + 注入预算 | design/fragments.md L34、L110-L113 | SP 的 Three Paths 是**产物量**分档，我方 light/heavy 是**提示词量**分档，两轴正交；SP 无"轻档"概念（fragments.md L52 已明确）。 |
| ③-7 | 代码级反模式拦截（太简单不落文档 → artifact_not_confirmed；薄卡 → 落库拒绝） | L50-L51；decomposing L86 | 把 SP 的 Red Flags"自律"升级为"硬拒"，不得因 vendor 原文而降级。 |

### ④ 明确不采用（7 条）

| # | 不采用对象 | SP 行号 | 不采用理由 |
|---|-----------|---------|-----------|
| ④-1 | Visual Companion 服务端/browser 本体（scripts/server.cjs、start-server.sh、stop-server.sh、frame-template.html、helper.js、visual-companion.md、--open 起浏览器） | L233-L235、L240、L249-L250 | ①本需求产物是"确定性注入的提示词"，非交互式 GUI；机器上不存在该 server，注入的指令会变成无法执行的动作；②启动本地 server/打开浏览器是副作用动作，超出"只注入提示词"的边界，也无法被页面插件审计；③成本高（1 份 guide + 4 个脚本），收益（弹窗可视化）与投资/流程类需求不匹配；④**只保留**"提议独立成一条消息"这一交互约束（②-6）。 |
| ④-2 | skill frontmatter 触发语义（name/description，"You MUST use this before any creative work"） | L1-L4 | REQ-31e11f 既定裁定：纪律必须**确定性注入**，不用 skill 自主 load（StagePromptSpec.ts L4-L6 注释原话）；注入由状态机触发，description 匹配在本仓是死代码。 |
| ④-3 | elements-of-style:writing-clearly-and-concisely skill 引用 | L208 | 该 skill 不在 superpowers 14 份内，本仓也不 vendor 它 → 引用会指向不存在的工具；且文风偏好属非纪律内容。 |
| ④-4 | docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md 目录约定 | L206 | 与 REQ 账本目录（docs/requirements/REQ-xxxxxx/）构成双事实源，看板/状态机/门禁都按 REQ id 索引；保留第二套目录会让"产物登记"失去唯一入口（改写见 ②-3）。 |
| ④-5 | Commit the design document to git | L100、L209 | 提交动作属仓库合流流程（CLAUDE.md：多 worktree 隔离、禁止在共享工作区提交），不属阶段纪律；且 API 侧无法保证 commit 质量与被跟踪范围。产物凭证改由 reqboard_submit 登记承担。 |
| ④-6 | Spike / Bounded 的产物豁免条款（No design doc, no spec file / No spec file, no implementation plan document） | L33、L44 | 与本仓产物闸门**直接冲突**：brainstorming→planning 要求 requirement 产物已确认，planning→decomposing 要求 plan 已批准。在本仓"轻"只能体现为 difficulty=light 的提示词精简 + 文档短，**产物不得省**。保留其行为纪律（spike 产出是结论、bounded 需先呈短设计并 STOP），去掉"不写文档"。 |
| ④-7 | Process Flow DOT 状态图本体 | L105-L147 | ①图内含"Invoke writing-plans skill"终态，逐字注入会给出**错误的交棒指令**；改写它又与 decomposition.md L64 的验收锚点"brainstorming/heavy 与 vendor 原文逐字一致（不得改写）"冲突；②本仓状态机 + 转移表已是权威事实源，再贴一张图会制造第二事实源与不一致风险；③改由附加片段的三行文字声明终态（②-5）。 |

**四类条目数：① 6 ／ ② 7 ／ ③ 7 ／ ④ 7（合计 27）。**

---

## 3. 我方当前 9 条清单 vs superpowers 差距总表

| # | 我方条目（行号 + 原文） | superpowers 对应 | 判定 | 补什么 / 怎么改 |
|---|------------------------|------------------|------|-----------------|
| 1 | 探索项目上下文（L39）：「先读相关文件/文档/最近变更，建立事实基础再开口问」 | Arch#1 L95 + L166 | **可保留** | 语义已等价（"最近变更"= recent commits）。无需改字。 |
| 2 | 范围评估先行（L40）：「请求涉及多个独立子系统时，先帮用户拆子项目——不要先扎进细节」 | L167-L168 | **需补强** | 补 SP 的落点句「每个子项目走自己的 spec → plan → 实施循环」→ 在本仓对应"各自 reqboard_create 立项、各自 requirement.md"。当前"拆子项目"在本仓没有出口，模型拆完不知道落到哪（表行 30 判"更弱"）。 |
| 3 | 澄清提问（一次一个问题）（L41-L42） | Arch#3 L97 + L169-L172 | **可保留** | 我方已含"一次一个"+"禁止一口气抛全套方案"，甚至更硬。可选微补"优先多选"（ask_user_question 的 options 天然支持）。 |
| 4 | 2-3 个方案对比（L43） | Arch#4 L98 + L174-L178 | **需补强** | 补 **YAGNI ruthlessly**（L179）——当前 0 覆盖，"方案里塞以后可能用的功能"是本节点最常见的范围膨胀源。 |
| 5 | 分节呈现设计（L44）：「需求文档分节写，每节先请用户确认再写下一节（禁止一次性全文）」 | Arch#5 L99 + L183-L186 | **需补强 + light 档降级** | ①补"篇幅随复杂度伸缩"标尺（L183-L184：几句话 ~ 200-300 词）；②**"禁止一次性全文"在 light 档应降级**为"短设计一次给出并等批准"（对齐 SP Bounded L39-L44），否则 light 档被迫走 heavy 仪式，"轻档省 token"失效（表行 34 判"更弱"）。 |
| 6 | 写需求文档（L45-L46）：「产出 requirement.md（docs/requirements/REQ-xxxxxx/，头部带 REQ id）；过程产物落进需求目录即自动登记（W4）」 | Arch#6 L100/L204-L209 | **可保留**（我方更强） | 保留 REQ 目录 + W4 自动登记；明确**不采用** SP 的 specs 路径（④-4）与 git commit（④-5），避免 t7 误 vendor。 |
| 7 | 文档自查（L47）：「占位符/矛盾/模糊/范围蔓延逐项过完再提交」 | Arch#7 L101 + L211-L219 | **可保留** | 4 项与 SP 一一对应（等价）。编排优化：把斜杠串拆成显式 4 子条，便于逐项勾选/机检（对应 SP 的编号形式）。 |
| 8 | 用户审阅文档（L48-L49）：「调 reqboard_ask_confirm（target=artifact, kind=requirement）弹框请人确认……先 reqboard_submit(kind=requirement) 登记产物」 | Arch#8 L102 + L221-L226 | **需补强** | 保留工具化闸门与"先 submit 再 ask_confirm"的顺序；补 SP L226 的回退环：「人要求改 → 改完重跑第 7 条自查 → 再请审」（当前缺失）。 |
| 9 | HARD-GATE（L50-L51）：「文档未经确认不得进入技术设计/实现动作……代码级也会拦 artifact_not_confirmed」 | L14-L20 + L54-L61 | **可保留（不得降级）** | 与 SP「ceremony scales; the approval gate never does」一致，且我方多一层代码级拦截。建议：把 SP L54-L61 的三例展开（todo/单函数/配置改动也要批准）作为 **heavy 附加片段**补入；light 档保留一句即可（本项永不随难度伸缩）。 |

**判定计数：可保留 5 条（1/3/6/7/9）｜需补强 4 条（2/4/5/8，其中第 5 条同时要求 light 档降级）｜应删除或降级 0 条（第 5 条的降级只作用于 light 档，heavy 保持）。**

---

## 4. 给 t7 的实施建议

> t7 既定口径（decomposition.md L60/L64）：heavy 档 = vendor superpowers v6.3.0（commit b36e082, MIT）原文；light 档 = 自写精简。以下建议在该口径内细化。

### 4.1 brainstorming/heavy：**vendor 整份** SKILL.md（不拆分）

落盘：src/domain/prompt/vendor/superpowers/brainstorming/SKILL.md（250 行 / **15,456 字节**，逐字，含 frontmatter）。

理由：
1. **验收锚点要求整份**：decomposition.md L64 断言"brainstorming/heavy 与 vendor 原文逐字一致（不得改写）"。若拆节 vendor，比对对象变成"残缺版原文"，锚点要么失效、要么必须额外维护一份"摘除清单"，可证伪性下降。
2. **体积可接受**：15,456 B 是本仓 heavy 里最大的主 skill（对照：writing-plans 7,053／finishing-a-development-branch 7,781／executing-plans 2,305／verification-before-completion 3,646），fragments.md L111 已定"主 skill 全文不裁"，估算 5–6k token，一次注入可承受。
3. **裁剪判断不该分散**：不采用的内容（frontmatter／Visual Companion 本体／DOT 图）若靠"拆节摘除"，6 个节点各裁各的，无法单测；整份 vendor + 一份集中式附加片段，边界清晰、可断言。
4. 唯一代价：原文含 frontmatter、Visual Companion 本体与 writing-plans 交棒，**必须靠附加片段纠偏**，故附加片段关键条目要做成 **floor（永不裁剪）**。

**注入顺序（三段，便于测试断言）**：
1. vendor 原文（逐字，第一段）
2. brainstorming/overrides 附加片段（第二段；首行声明「以下条目覆盖上文与本仓冲突之处」）
3. common/iron-rules（floor，最后；闸门措辞）

顺序理由：①"教科书原文在前、本仓接线图在后"符合显式后置覆盖的注意力分布；②若反序，原文 L103/L149-L154 的 writing-plans 终态会压过我方 reqboard 交棒，L240 的 start the server with --open 会诱导不存在的副作用动作。

### 4.2 附加片段 brainstorming/overrides 要叠加哪些我方独有内容（6 条，约 1.5–2.5 KB，全部 floor）

1. **交棒覆盖**：writing-plans skill → 「下一步：planning —— 调 reqboard_ask_confirm(target=artifact, kind=requirement)，肯定答复自动落章并推进；未获确认不得进入 planning/拆分/实施」。覆盖 SP L103/L124/L145/L228-L231（对应 ②-5）。
2. **落盘覆盖**：docs/superpowers/specs/... → docs/requirements/REQ-xxxxxx/requirement.md（头部带 REQ id）+ reqboard_submit(kind=requirement) 登记；**不要求 agent git commit**。覆盖 SP L100/L206/L209（②-3、④-4、④-5）。
3. **Visual Companion 本体禁用**：不得启动任何 server/浏览器（原文 L240 的 start the server with --open 不适用）；如需可视化，用**独立一次弹框**提议（只含提议、不带其他内容），并按"看图是否比读字更清楚"逐问题判断。覆盖 SP L96/L237-L247（②-6、④-1）。
4. **产物豁免无效**：SP L33/L44 的 "No design doc, no spec file" / "No implementation plan document" 在本仓不适用——轻路径 = 文档短 + difficulty=light 提示词精简，**产物不得省**（④-6）。
5. **任务语义**：SP L77-L78 的 "create a task for each item" 在本节点指**节点内可勾选清单**（注入文本自查），不是 reqboard_decompose 任务卡（任务卡属 decomposing 节点，W7 边界，②-2）。
6. **闸门兜底**：HARD-GATE + 代码级拦截 artifact_not_confirmed；"太简单不用走流程"由代码拒绝，不由模型自裁（③-4、③-7）。
7. （可选第 7 条）**节点归属纠偏**：SP L186「Cover: architecture, components, data flow, error handling, testing」在本仓属 **planning** 节点（我方 planning L59-L64），brainstorming 阶段不得越界写技术设计（fragments.md L96-L103 的节点归属表）。

### 4.3 brainstorming/light：自写 5 条（≤2500 字符，不 vendor）

沿用 fragments.md L72-L81 的 L1-L4，并按本次对照新增 L5：

1. **L1 一句话目标 + 可证伪判定标准**（对齐 SP L183 的"几句话"档）。
2. **L2 ≤3 条范围边界**（做什么 / 不做什么）。
3. **L3 轻路径依据 + 可升级声明**：「改动面小、无新决策点」+「发现出现第二个未定决策 / 要动架构 / 要新增子系统 → 立即停手转 heavy」——这是 SP 三路径单向棘轮（L50-L52）在本仓 light/heavy 轴上的等价物。
4. **L4 批准闸门 + 下一步声明**：reqboard_ask_confirm 交棒 planning（同 H7/H8）。
5. **L5（新增，防误推）**：轻档 ≠ 无产物——requirement.md 仍必须产出并经确认；**明确否掉** SP L33/L44 的"无 spec"直觉（④-6 的落点）。

light 不得包含：三路径长篇说明、分节设计模板、Visual Companion 提议脚本、示例对话（fragments.md L81）。

### 4.4 其余五个节点 ↔ superpowers skill 映射（14 份全量核对）

14 份 SKILL.md（origin/main，字节数为实测）：brainstorming 15,456／writing-plans 7,053／executing-plans 2,305／verification-before-completion 3,646／finishing-a-development-branch 7,781／test-driven-development 9,015／subagent-driven-development 32,339／using-git-worktrees 6,813／dispatching-parallel-agents 6,078／requesting-code-review 2,956／receiving-code-review 6,203／systematic-debugging 9,465／writing-skills 26,360／using-superpowers 3,108。

| 我方节点 | 对应的 superpowers skill | 角色 | 说明 |
|----------|--------------------------|------|------|
| brainstorming | **brainstorming**（15,456） | 主（heavy=vendor 全文） | 本对照对象 |
| planning | **writing-plans**（7,053） | 主 | SP 无独立"技术设计"skill，writing-plans 含计划文档结构与提交前自查，作 heavy 主体 |
| decomposing | **无对应** | — | 14 份里没有"拆分/任务 DAG/卡质量"skill；writing-plans 内的任务表是最近邻，但"卡四要素 + 代码级拒薄卡"是我方独有 → heavy 只能自写（风险见 4.5） |
| implementing | **executing-plans**（2,305） | 主 | 附属（按需，单次最多挂一个）：test-driven-development 9,015／subagent-driven-development 32,339／using-git-worktrees 6,813／dispatching-parallel-agents 6,078／requesting-code-review 2,956／receiving-code-review 6,203 |
| accepting | **verification-before-completion**（3,646） | 主 | 附属：requesting-code-review（含 code-reviewer.md 评审提示词）／receiving-code-review |
| archived | **finishing-a-development-branch**（7,781） | 主 | 归档/收尾纪律最近邻；我们的 ARCHIVE_DOC_RULES 目录清单为其本地化补充 |
| 横切（不占节点） | **systematic-debugging**（9,465）／**writing-skills**（26,360）／**using-superpowers**（3,108） | 建议落 common/ 或类型档 | fragments.md L98/L102 已如此安排：systematic-debugging 走排障场景、writing-skills 走"写提示词本身"、using-superpowers 提供"先分类宣布"的元纪律 |

### 4.5 一处需要上游拍板的风险（诚实列出）

decomposition.md L60 的既定口径是"六节点 light/heavy，heavy=vendor superpowers 原文"，但 **decomposing 在 14 份里无对应 skill**（writing-skills 与 using-superpowers 也不是节点 skill）。建议 t7 把口径细化为三类：
1. **有主 skill 的节点**（brainstorming/planning/implementing/accepting/archived）→ heavy = vendor 主 skill 原文；
2. **无对应的节点**（decomposing）→ heavy = 自写，并显式登记为"superpowers 无对应"的例外，接受"重档非 vendor"，门禁断言不能写"逐字一致"；
3. **附属 skill 不进 heavy**，只在节点内出现对应场景时按需注入（fragments.md L53/L112 已定）。

该点超出本对照（只读比对）的范围，需上游（t7 执行者/需求属主）确认后再落地。

---

## 附：本次对照的可核验命令

1. 基准来源：cd /Users/yunpeng/.claude/skills/superpowers && git show origin/main:skills/brainstorming/SKILL.md > /tmp/sp-brainstorming-latest.md（校验：wc -c = 15456，与 origin/main 一致；git log -1 origin/main = b36e0829c6d0140e93cfef2ca599b1b07d4a7797）
2. 章节数：grep -c '^#' /tmp/sp-brainstorming-latest.md = 9；grep -nE '^\*\*' 得 15 处粗体子节
3. 我方段落：StagePromptSpec.ts L34-L52（brainstorming）
4. 结论计数：本文件 §1 小结表（44 行：等价 14／我方更强 2／我方独有 1／更弱 6／完全缺失 21）
