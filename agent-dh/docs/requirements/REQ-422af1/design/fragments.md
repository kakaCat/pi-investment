# REQ-422af1 技术设计 · 分片库与内容规范

> 阶段：planning · 窗口 w-41e7e4cd · 配套：design/architecture.md

## 1. 分片元数据契约

    Fragment = {
      id: string           路径去扩展名，如 brainstorming/heavy、common/red-flags
      stage: StageKey | 通配星
      difficulty: light | heavy | 通配星
      category: Category | 通配星
      priority: number | floor      // floor = 清单/闸门/红旗，预算裁剪永不触碰
      text: string                   // 正文（构建期内联）
    }

约定：**id 唯一**；**每个分片至少被一条路由用到**（否则门禁 4 判孤岛）；分片之间不写互相矛盾的指令（同一次注入里并存即冲突）。

## 2. 分片清单（P0：与现状等价的兜底档）

P0 **只做搬运**：把现有 6 份阶段提示词原样落到 (stage, 星, 星) 兜底档，文本逐字不变（INV-7）。

| 分片 id | 层 | 来源 |
|---------|----|------|
| brainstorming/星 | ④ | 现 StagePromptSpec.brainstorming |
| planning/星 | ④ | 现 planning |
| decomposing/星 | ④ | 现 decomposing |
| implementing/星 | ④ | 现 implementing |
| accepting/星 | ④ | 现 accepting |
| archived/星 | ④ | 现 archived |
| common/iron-rules | ⑤ | 铁律（批准闸门永不伸缩、清单纪律） |

## 3. 分片清单（P1/P2：分化档）

**六个节点**（brainstorming / planning / decomposing / implementing / accepting / archived）**每个都要有 light 与 heavy 两档**——难度决定"仪式强度"，与节点无关（用户 2026-09-17 明确："每个节点都要加载不同难度的提示词"）。

| 节点 | light（简单任务的仪式） | heavy（难任务的仪式） |
|------|----------------------|---------------------|
| brainstorming | 一句话目标 + 边界 + 闸门（L1-L4） | 三路径分类宣布 + 按路径清单 + 红旗表 + YAGNI + 分节篇幅 + 回退环 + 闸门 + 终态（H1-H8） |
| planning | 目标 / 步骤 / 验收 三行即可 | 设计文档索引 + 数据层与选型结论 + 测试用例 + 迁移与回滚 + 提交前自查 |
| decomposing | 直接列任务卡，卡内给 acceptance | 批次与依赖（depends_on）+ 每卡 implementation + 边界校验（不超范围、卡可独立验收） |
| implementing | 直接改 + 自测通过即报 | 先读文档 → 小步提交 → TDD/独立验证 → 不夹带无关重构 → 逐项对照验收标准 |
| accepting | 自检清单过一遍 | 逐项给可复核证据 + 独立复核（不复用自述）+ 验收单断点续验 + 未过项返工 |
| archived | 目录 + 文档清单 + 去向 | 合并去向必填 + 项目说明书更新点 + wiki 挂链自检 + 索引条目 |

类型档（category 差异）在 P2 覆盖**全部六个节点**（每节点该追加什么见 §6）。

## 3.5 内容来源与"披露"语义（2026-09-17 定稿）

- **节点 = 选择器**：状态机已经决定了当前该用哪份内容，因此**不需要任何 skill 匹配/检索机制**（DSH 的 skill 工具是模型自主 load，本需求不用它做主纪律——REQ-31e11f 既定裁定）。
- **披露 = 注入方式**：到哪个节点才注入哪份内容（按节点分批），并在注入时按预算裁剪。
- **heavy 档 = superpowers 原文**（vendor，不改写）：brainstorming ← superpowers/brainstorming；planning ← writing-plans；implementing ← executing-plans；accepting ← verification-before-completion；archived ← finishing-a-development-branch；横切 ← systematic-debugging / writing-skills。
- **light 档 = 自写精简**（不 vendor，因为 superpowers 没有"轻档"概念）。
- **附属 skill 按需披露**：TDD / subagent-driven-development / using-git-worktrees / dispatching-parallel-agents / requesting+receiving-code-review 挂在**节点内子步骤**上，出现对应场景才注入（这是"渐进式披露"的真正落点）。

vendor 目录（含 ATTRIBUTION、版本号、MIT 许可原文）：

    src/domain/prompt/vendor/superpowers/<skill-name>/SKILL.md
    src/domain/prompt/vendor/superpowers/ATTRIBUTION.md   ← 来源 repo + tag/commit + 许可 + 抓取时点
## 4. brainstorming heavy 的必备要素（= superpowers 原文，逐项核对）

| # | 要素 | 要求 |
|---|------|------|
| H1 | **三路径分类**（Spike / Bounded / Architectural） | 开工先分类并**宣布**，人可否决；拿不准取更重的那条；**单向棘轮**（发现更复杂可升级，不许降级） |
| H2 | 按路径的分支清单 | 三条路径各自一份可勾选清单，不是一份通用清单 |
| H3 | Red Flags 表 | 列出"该停下来重判"的信号（范围悄悄变大、出现第二个未定决策、要动架构却没写 spec） |
| H4 | YAGNI 纪律 | 明确禁止把"以后可能要"的东西写进本次设计 |
| H5 | 分节篇幅伸缩 | 设计文档按复杂度分节（架构/组件/数据流/错误处理/测试）；要素齐全、篇幅随复杂度 |
| H6 | 回退环 | 设计被否 / 文档要求改 / 人插入新约束 → 明确回到哪一步、重新确认什么 |
| H7 | 批准闸门措辞 | "仪式随任务伸缩，批准闸门永不伸缩"；未获批不得进入下一节点 |
| H8 | 终态 | 本节点结束**只能**交棒给 planning（不得直接跳到实施） |

## 5. brainstorming light 的必备要素

| # | 要素 |
|---|------|
| L1 | 一句话目标 + 判定标准（可证伪） |
| L2 | 3 条以内范围边界（做什么 / 不做什么） |
| L3 | 承认这是轻路径的**依据**（改动面小、无新决策点），并允许升级为 heavy |
| L4 | 批准闸门 + 下一步声明（同 H7/H8） |

**light 不得包含**：三路径长篇说明、分节设计模板、示例对话——那些是 heavy 的内容（这正是省 token 的来源）。

## 6. 类型差异的写法（同一节点内 category 只做"提示差异"）

| 类型 | 追加提示（片段内容） |
|------|---------------------|
| bug | 先复现再改；必须给回归测试；禁止顺手重构；根因不清不许动手 |
| refactor | 先盘依赖与调用方；必须给"行为等价"的证据；一次只改一类东西 |
| feature | 先定接口与数据契约；迁移与兼容路径要写；验收要能跑 |
| spike | 目标是"回答一个问题"；产出是结论不是代码；限时；不写生产级实现 |
| doc | 只改文档；结论进项目说明书对应章节；注意 wiki 挂链 |
| chore | 最小改动；不夹带业务逻辑变更 |

## 7. skill ↔ 节点映射（落地到哪些分片）

| 节点 | 吸收要点 | 落点 |
|------|---------|------|
| brainstorming | brainstorming（三路径/红旗/YAGNI/篇幅）+ using-superpowers（先分类宣布） | brainstorming/heavy, brainstorming/light, common/iron-rules |
| planning | writing-plans（计划四要素 + 提交前自查） | planning/* |
| implementing | executing-plans + TDD + subagent-driven-development + worktrees + dispatching-parallel-agents | implementing/* |
| accepting | verification-before-completion + requesting/receiving-code-review | accepting/* |
| 横切 | systematic-debugging（排障）、writing-skills（写提示词本身） | common/* + implementing/accepting 的类型档 |
| 收尾 | finishing-a-development-branch | archived/* |

## 8. 注入预算（字符数为口径，token 的代理指标）

| 档 | 目标 | 说明 |
|----|------|------|
| P0 | **不设裁剪**（预算 = 现有文本实测长度上限） | 保证零行为变更（INV-7）；先量再收 |
| light | ≤ 2500 字符 | 简单任务的注入上限 |
| heavy | **主 skill 全文不裁**（如 brainstorming 15,456 字符）；附加片段与按需片段可裁 | 原文档全文是 heavy 的价值所在，裁正文等于回到"要点版"；**实测值：单次注入预算 DEFAULT_PROMPT_BUDGET = 24000 字符**（T7 由 8000 上调，因 heavy 最大解析结果 17,193 字符，预算必须留余量） |
| 按需 | 每个附属 skill 全文（单份 2,305 ~ 32,339 字符） | 仅在节点内出现对应场景时注入；**同一次注入最多挂一个按需片段** |
| floor | 不裁 | 清单/闸门/红旗三类；连保底都超则响亮报超限 |

## 9. 编写规范

- 第二人称祈使句（"先…再…"），不用"建议/可以考虑"这类软措辞。
- 清单用可勾选形式（- [ ] 或编号），便于逐项执行与门禁检查——**散文步骤正是这次要治的病**。
- 每个节点分片**末尾固定一行**：下一步：next stage —— 用 tool 交棒；未获批准不得进入。
- 工具名只写真实注册名（reqboard_create/status/move/decompose/task_move/task_report/submit/ask_confirm/accept_sheet），门禁 2 兜底。
- 分片之间不重复同样内容（重复 = 该提到 common/，否则 token 白花）。
