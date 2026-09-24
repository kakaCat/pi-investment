---
requirement_refs: [FR-1, FR-2, FR-3, FR-5, FR-8, FR-10, FR-12]
---

# 后端设计（REQ-260922213356-4a45）

> 读者：实现本需求的 agent/开发。全部改动在 `packages/web/dsh-pmboard`，无 HTTP 层改动。
> 编号 S-x 供 test-cases「被测对象」引用。

## 服务与接口实现 <!-- serves: FR-1, FR-2, FR-3, FR-5 -->

| 编号 | 类型 | 名称 | 职责说明 | 输入 | 输出 | 调用方 | 依赖 | serves |
|---|---|---|---|---|---|---|---|---|
| S-1 | 函数 | `resolveNodeTemplates` | 按节点+类型查表返回应产出的模板条目 | stage (PromptStage), category (Category\|undefined) | `readonly TemplateRef[]`（空=无） | S-3/S-4、三个注入点 | I-1 契约、门禁类型常量 | FR-2, FR-7 |
| S-2 | 函数 | `resolveUpstreamDocs` | 从台账投影出上游必读产物地址 | requirement (RequirementRecord\|undefined), stage (PromptStage), currentTask? (TaskRecord) | `readonly DocRef[]`（空=无） | S-3/S-4 | 台账只读投影 | FR-5 |
| S-3 | 函数 | `renderAddressSection` | 把两张清单渲染成地址段文本；空集返空串 | `AddressSectionInput` | string | S-4 与三个注入点 | S-1, S-2 | FR-3, FR-4, FR-13 |
| S-4 | 函数 | `augmentResolvedPrompt` | 把地址段折进 ResolvedPrompt；空集恒等返回 | resolved (ResolvedPrompt), input (AddressSectionInput) | ResolvedPrompt | 三个注入点 | S-3 | FR-3, FR-4, FR-8 |
| S-5 | 函数 | `resolveTemplateRoot` | 解析模板根绝对路径（配置覆盖 > 包根解析） | config (`{templateRoot?: string}`), moduleDir (string) | `string \| undefined`（undefined=不可用，响亮留痕） | 组合根 `apply()` | `node:path`（**仅组合根/adapters**，不进 domain） | FR-3 |
| S-6 | 函数 | `resolveStagePromptForGate` | H3 的 verdict 分流：肯定取词、非肯定跳过 | ctx (ConfirmContext), requirement, resolve (注入的取词入口) | `{kind:'inject',text}` \| `{kind:'skip',code:'negative_verdict'}` | `gate/handlers/h3-inject.ts` | `resolveStagePrompt`、`stageEnabledFor` | FR-10 |
| S-7 | 函数 | `buildNodeInputPackage`（地址节追加） | 输入包追加「本节点文档」小节 | `NodeInputPackageInput`（+ templateRoot） | `NodeInputPackage`（text 含地址节） | `use-cases/IsolateNodeContext.ts` | S-4 | FR-3, FR-8, FR-12 |

> 类型说明：`函数`=纯函数无副作用；`服务`/`模块`本需求不新增（不新增端口、不新增 I/O 实现）。

## 数据流 <!-- serves: FR-3, FR-8, FR-12 -->

**事件 A：绑定窗口每回合注入（系统提示词段）**

```
事件：systemPrompt.assemble() → section 'reqboard:capture' 求值
  ↓
步骤 1：boundSectionText(ledger, context, injectionLog)
  ├─ windowKey 不可得 / 无进行中需求 → 返回 ''（零噪音，结束）
  └─ 有进行中需求 → 继续
  ↓
步骤 2：resolveStagePrompt({stage, category, requirement})  ← 现状
  ↓
步骤 3：renderAddressSection({stage, category, requirement, templateRoot})  ← 新增
  ├─ 空集 → section = ''
  └─ 非空 → 指针段文本
  ↓
步骤 4：augmentResolvedPrompt(resolved, input)（空集返回原对象）
  ↓
步骤 5：injectionLog.record(…charCount=增强后长度)（FR-8 记账）
  ↓
【副作用】无文件写入（除既有留痕）；模板文件不被打开
```

**事件 B：闸门作答 → 后置链 H1→H2→H3→H4**

```
事件：用户在闸门作答（弹框或文字 evidence）→ GatePostChain.runPending
  ↓
步骤 1：H1 advance：以台账实时状态判 verdict
          需求 status === ctx.to → affirmative；否则 negative
  ↓
步骤 2：H2 compact：可选压缩 → 压缩时构造节点输入包（见事件 C）
  ↓
步骤 3：H3 inject：resolveStagePromptForGate(ctx, requirement)   ← 改动：先判 verdict
  ├─ negative  → skip(negative_verdict)：不取词、不写 scratch、不留痕   ← FR-10
  └─ affirmative → 取词 → renderAddressSection → augmentResolvedPrompt
                   → injectionLog.record(charCount 含地址段)
                   → scratch.promptText = 增强后的 text
  ↓
步骤 4：H4 resume：按 D5 分流
  ├─ H2 真压缩过 → 只发作答摘要（地址已在输入包里）
  ├─ H2 跳过/降级 + affirmative → 摘要 + 纪律全文（含地址段）
  └─ negative → **摘要 + 用户意见**（不附任何纪律块）   ← FR-10
  ↓
【副作用】向窗口投递一条消息（既有 AgentDeliverer）；无其他
```

**事件 C：节点边界压缩 → 节点输入包（唯一新起点）**

```
事件：节点边界触发隔离/压缩（nodeIsolation 开启时）
  ↓
步骤 1：buildNodeInputPackage({stage, category, requirement, requirementDoc, requirementDocPath, …})
  ↓
步骤 2（新增）：渲染「## 本节点文档（模板地址 / 上游必读）」小节
          = renderAddressSection(...)（与事件 A/B 同一函数）
  ├─ 空集 → 不追加小节（与改造前逐字节一致）
  └─ 非空 → 追加在「## 需求文档」小节之后
  ↓
步骤 3：输入包 text 作为模型可见面；下一回合系统段重装仍含同一份地址段（双落点）
  ↓
【副作用】无；输入包是纯文本
```

**三路径一致性**：事件 A/B/C 的地址段来自**同一个纯函数**，输入同为 `(stage, category, requirement, currentTask?, templateRoot)`；
单测对同一输入断言三处输出**逐字一致**（FR-8/FR-12）。

## 关键逻辑 <!-- serves: FR-2, FR-3, FR-5 -->

### S-1 地址解析逻辑 <!-- serves: FR-2, FR-7 -->

**功能**：给定 `(stage, category)`，返回该节点该类型应产出的模板条目清单。

**处理步骤**：
1. **节点闸**：`stageEnabledFor(category, stage)` 为 false → 返回 `[]`（未启用节点不产文档，也不给地址）；
2. **取通用档**：`NODE_TEMPLATES[stage]['*']`（若存在）；
3. **取类型档**：`NODE_TEMPLATES[stage][category]`（若存在）；
4. **合并**：类型档在前、通用档随后，按 `id` 稳定去重（同 id 只保留首个）；
5. **返回**：`readonly TemplateRef[]`（可能为空数组）。

**边界条件**：
- `category === undefined` → 按 `DEFAULT_CATEGORY`（feature）；
- 该类型在该节点"无文档"（bug 的 design）→ 返回 `[]`，**不编造地址**；
- 表里配了但文件不存在 → 本函数不管（守护单测负责），运行时**不臆造**。

**示例**：`(design, feature)` → 5 条（architecture/data-model/interfaces/test-cases/use-cases）；
加上 `sides=backend` 的条件条目 backend → 6 条；`(design, bug)` → `[]`。

### S-2 上游必读解析逻辑 <!-- serves: FR-5 -->

**功能**：给定需求与节点，返回"开工前该先读"的已登记产物地址。

**处理步骤**：
1. `requirement === undefined` → 返回 `[]`（无归属需求，不臆造）；
2. 取 `requirement.artifacts` 中**已确认/已登记**且属于上游节点的产物（brainstorming 的 requirement.md、design/*.md、decomposing 的 decomposition.md 等）；
3. 实施节点附加 `currentTask.cardDoc`（当前任务卡文档）与该卡引用的设计文档；
4. 逐项转 `DocRef{kind,path,title}`；`title` 由 `shared/artifact-labels.ts` 的既有中文名映射给出（缺映射回落 kind 原文）；
5. 返回（可能为空数组）。

**边界条件**：
- 台账里产物**未登记** → 不列出（不是"文件不存在就跳过"，而是**以台账为唯一事实源**）；
- `cardDoc` 为空 → 不列出任务卡，但其余上游正常列出；
- 同一 path 重复登记 → 去重。

### S-3 渲染逻辑（空集空串 + 指针形态） <!-- serves: FR-3, FR-4, FR-13 -->

**功能**：把 S-1/S-2 的结果渲染成一段 markdown；两清单都空 → **返回空串**。

**处理步骤**：
1. `const tpl = resolveNodeTemplates(...)`，`const up = resolveUpstreamDocs(...)`；
2. `tpl.length === 0 && up.length === 0` → `return ''`（**早返回，不产生任何空白/表头**）；
3. 非空 → 按 interfaces.md I-3 的逐字模板拼装：
   标题 + 「产出模板」块（`title：{templateRoot}/{relPath} —— {purpose}`）+ 「上游必读」块（含纪律句「先读再动手」）；
4. 校验并规范化 `templateRoot`：必须是绝对路径且不以 `/` 结尾（尾部斜杠归一，避免 `//`）；
5. `relPath` 只允许来自映射表；渲染前断言不含 `..`、不以 `/` 开头（形态护栏）。

**边界条件**：
- `templateRoot === undefined` → 由调用方（组合根）判为不可用，**整段不注入 + 留痕**（见错误处理）；
- `title/purpose` 缺字（配置漏写）→ 守护单测红（不是运行时空串）。

**示例**（feature design，节选）：
```
## 本节点文档（模板地址 · 先读再动手）

产出模板（绝对地址，用 read 直接打开照写）：
- 架构设计：/abs/path/templates/design/architecture.md —— 整体架构/技术选型/模块职责
上游必读（先读再动手）：
- 需求说明：docs/requirements/REQ-xxx/requirement.md
```

**性能指标**：纯函数，O(条目数)；条目数 ≤ 8，单次 < 1ms。

### S-4 装配（augmentResolvedPrompt） <!-- serves: FR-3, FR-4, FR-8 -->

**功能**：把地址段折进 `ResolvedPrompt`，使留痕与投递文本同源。

**处理步骤**：
1. `const section = renderAddressSection(input)`；
2. `section === ''` → `return resolved`（**引用相等**，FR-4 逐字节兼容的可测形态）；
3. 否则 `return { ...resolved, text: resolved.text + '\n\n' + section, charCount: 新长度 }`；
4. `fragmentIds/routeKey/hitLevel/trimmed/overBudget/difficultyReasons` 原样保留。

**边界条件**：
- `resolved.text === ''`（取词为空）→ 由 H3 既有降级分支拦截，轮不到本函数；
- 地址段超预算？地址段**不进预算裁剪**（它不在分片库里），但总增量必须 < 2KB（性能节）。

### S-6 H3 verdict 分流 <!-- serves: FR-10 -->

**功能**：确认门作答后，决定是否把"作答后所处阶段"的纪律注入当前窗口。

**处理步骤**：
1. 既有闸：`isPromptStage(ctx.to)`、无可归属需求、`stageEnabledFor` 失败 → 沿用现状 skip；
2. **新增**：`ctx.verdict === 'negative'` → `return { kind: 'skip', code: 'negative_verdict', reason }`——
   不调用 `resolve`、不写 `scratch.promptText`、不写注入留痕；
3. `ctx.verdict === 'affirmative'` → 调 `resolve(...)` 取词（现状不变）；
4. 取词结果为空 → 沿用现状 `degraded(empty_prompt)`；
5. **新增**：取词成功 → `augmentResolvedPrompt(resolved, input)` → 留痕用增强后的 `charCount` → `scratch.promptText = 增强文本`。

**边界条件**：
- `ctx.verdict` 为 undefined（H1 未跑到/异常）→ **按 negative 处理**（保守：不注入下一节点纪律）；
- 肯定分支的输出必须与改造前**逐字一致**（防"修反"），由基线测试断言。

### 三个注入点的改动清单 <!-- serves: FR-3, FR-8, FR-12 -->

| 注入点 | 文件 | 改动（做什么/不做什么） |
|---|---|---|
| 系统提示词段 | `src/application/internal/capture-section.ts` | `boundSectionText` 中在 `resolved` 入段前调 S-4；空集时行为逐字不变；**不新增 section** |
| 闸门链 | `src/application/gate/handlers/h3-inject.ts` | 取词前加 S-6 分流；取词后调 S-4；HANDLER_ORDER 不变 |
| 节点输入包 | `src/application/internal/node-input-package.ts` | `buildNodeInputPackage` 追加「本节点文档」小节（复用 S-3，不复制文案）；空集不追加 |
| 唤醒收尾 | `src/application/gate/handlers/h4-resume.ts` | 非肯定分支不附纪律块（只发摘要 + 意见）；肯定分支不变 |

## 错误处理 <!-- serves: FR-4, FR-10 -->

| 错误类型 | 边界 | 错误标记 | 处理 | 重试策略 | 降级方案 |
|---|---|---|---|---|---|
| 节点未启用 / 类型无模板 | S-1 | 无（合法态） | 返回空集 → 空串 | 不重试 | 注入文本与改造前逐字节一致（FR-4） |
| 上游产物未登记 | S-2 | 无（合法态） | 该项不列出 | 不重试 | 只注入剩余项；无项则空串 |
| 地址映射漏配 / 死链 | 守护单测 | 单测失败（红） | 阻断提交/CI，不进运行时 | 修表后重跑 | 运行时不兜底（不臆造地址） |
| `templateRoot` 不可用 | 组合根 S-5 | 留痕 `address_section_disabled` | 地址段整体不注入 + 响亮留痕 | 不重试 | 回落到改造前行为 |
| 渲染内部异常 | S-3 | 由调用方降级 | 沿用既有注入降级留痕 | 不重试 | H3 就地 `degraded`；系统段跳过该段 |
| 非肯定项误注入下一节点纪律 | S-6 | `skip(negative_verdict)` | 直接跳过取词 | 不重试 | 只发作答摘要 + 用户意见（FR-10） |

**错误降级原则**：
- 用户/业务合法态（空集）**不是错误**，不记 error 级日志，不弹告警；
- 配置/映射错误（死链、根不可用）**必须响亮**：开发期红灯 + 运行时留痕；
- 一切降级都不得改变"空集逐字节一致"这一底线。

## 数据库设计 <!-- serves: FR-1 -->

**无表结构变更**：不新增/修改表、字段、索引、约束（详见 data-model.md §版本兼容）。
本需求只**读**既有 `requirement.artifacts` 与 `task.cardDoc`，不写任何持久化数据。
因此本节无需 SQL 与索引设计；迁移步骤为空（无迁移）。

## 性能考量 <!-- serves: FR-3, FR-13 -->

| 指标 | 目标 | 当前实测 | 瓶颈分析 | 优化方案 |
|---|---|---|---|---|
| 地址段增量 | < 2KB / 次注入 | 未实现 | 条目数 × 指针行长度 | 指针行只放「名 + 一句话用途 + 地址」；purpose ≤ 40 字；不内联正文 |
| 解析+渲染耗时 | < 1ms | 未实现 | 无（纯函数，无 I/O） | 常量表查表 O(条目数)；不读盘 |
| 模板体量相关性 | 与模板总大小**无关** | 未实现 | — | 只注入地址，不注入正文（FR-13） |
| 压缩路径成本 | 与未压缩路径同阶 | 未实现 | 输入包体积 | 只追加一小节；空集不追加 |

**瓶颈分析**：最大成本来自**指针行条数**（feature design 6 条 + 上游若干），实测应在 1KB 量级；
不再随 templates/ 增长而增长（这是与"模板全文注入"的本质差异）。

## 安全设计 <!-- serves: FR-2, FR-5 -->

### 鉴权 <!-- serves: FR-5 -->

| 调用方 | 鉴权要求 | 权限校验规则 | Token 格式 |
|---|---|---|---|
| 三个注入点 → S-1/S-2 | **不适用**（进程内函数） | 上游地址仅限本窗口绑定需求的台账 | 无 |
| 上游地址读取 | 沿用既有 reqboard 工具层权限 | 台账投影只读，不跨需求读取 | 无 |

### 输入校验 <!-- serves: FR-2 -->

| 参数 | 校验规则 | 拒绝示例 | 理由 |
|---|---|---|---|
| `relPath` | 白名单（映射表内值）；拒绝 `..`、以 `/` 开头、空串 | `../../etc/passwd` | 防路径穿越（地址会被注入并被人 read） |
| `templateRoot` | 必须绝对路径；尾部斜杠归一 | `templates`（相对） | RISK-1：相对路径 read 打不开，且口径随 cwd 漂移 |
| `requirement` | 只接受本窗口绑定需求对象 | 伪造的跨需求对象 | 防越权读取他人需求路径 |
| `stage/category` | 枚举收窄（收窄失败响亮抛错） | `'design2'` | 防越界值静默当通配 |

### 敏感信息 <!-- serves: FR-2 -->

| 字段 | 是否敏感 | 处理方式 |
|---|---|---|
| 模板文件磁盘路径 | 否 | 可全量注入（本地部署，无外网暴露） |
| 需求文档路径 | 否 | 可全量注入（工作区相对路径） |
| 台账内业务数据（持仓/账户） | 是 | **不进地址段**——只注入 kind/path/title |
