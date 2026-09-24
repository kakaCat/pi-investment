---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13]
---

# 拆分计划（REQ-260922213356-4a45）

> 目标一句话：把「文档模板」从只有人知道位置的磁盘文件，变成**节点入口可发现**的格式事实源——
> 节点注入文本里附带「本节点该产出的模板绝对地址」+「开工前该读的上游产物地址」，成本恒定；
> 并修掉「非肯定答复却注入下一节点纪律」这一本轮实测缺陷。
>
> 做法一句话：新增一张**静态地址映射表**（节点×类型 → 模板相对名）+ 一个**守护单测**（路径存在 /
> 与门禁文档集同源 / 漏配报警），由三处注入点共用一个**纯函数**把地址段折进既有注入文本；
> H3 按 `ctx.verdict` 分流（非肯定项不取词），H4 非肯定分支只发作答摘要。
>
> 本计划须**人批准**后才能落任务卡（reqboard_decompose）。**覆盖不齐不许批**。

## 编号口径

| 编号 | 出自 | 指什么 |
|---|---|---|
| FR-x | requirement.md 功能点表 | 需求条款（本需求 FR-1 ~ FR-13） |
| I-x | design/interfaces.md 接口清单 | 进程内函数契约（I-1 ~ I-5） |
| S-x | design/backend.md 服务与接口实现 | 函数/改动点（S-1 ~ S-7） |
| T-x | design/data-model.md 表/实体 | 代码常量实体（T-1 ~ T-3；本需求零表变更） |
| UC-x | design/use-cases.md 场景总览 | 用户场景（UC-1 ~ UC-7） |
| TC-x | design/test-cases.md 用例表 | 测试用例（TC-1 ~ TC-14） |
| t-x | 本文档任务表 | 任务（**本计划用大写 T-1 ~ T-8 作计划 key**，见「设计偏差 D-0」） |

## 改动盘点（新增 / 修改 / 删除）

### 新增（9 个源/测试文件）

| 文件 | 内容 | 对应 |
|---|---|---|
| `packages/web/dsh-pmboard/src/domain/template/types.ts` | `TemplateRef` / `DocRef` / `AddressSectionInput` / `UpstreamSource`（domain 局部结构类型，**不 import shared**） | I-3、T-1、T-2 |
| `packages/web/dsh-pmboard/src/domain/template/registry.ts` | `NODE_TEMPLATES` 静态常量表（节点×类型 → 条目）；纯常量、零 I/O | FR-1、T-1、T-3 |
| `packages/web/dsh-pmboard/src/domain/template/resolve.ts` | `resolveNodeTemplates` / `resolveUpstreamDocs`（S-1 / S-2） | I-1、I-2 |
| `packages/web/dsh-pmboard/src/domain/template/render.ts` | `renderAddressSection`（S-3；空集返空串） | I-3 |
| `packages/web/dsh-pmboard/src/domain/template/index.ts` | 目录 barrel（唯一 import 面） | — |
| `packages/web/dsh-pmboard/src/application/internal/injection-address.ts` | `augmentResolvedPrompt`（S-4；空集返原引用） | I-4 |
| `packages/web/dsh-pmboard/src/adapters/TemplateRoot.ts` | `resolveTemplateRoot(config, moduleDir)`（S-5；`node:path` 仅在此） | FR-3 |
| `packages/web/dsh-pmboard/tests/template-address.test.ts` | 守护单测（TC-1~8、TC-12、TC-13） | FR-1/2/4/5/7 |
| `packages/web/dsh-pmboard/tests/template-address-injection.test.ts` | 注入点/压缩两路径/非肯定分流（TC-9~11、TC-14） | FR-3/8/9/10/12 |

### 修改（13 个文件）

| 文件 | 改动 | 对应 |
|---|---|---|
| `packages/web/dsh-pmboard/src/application/internal/capture-section.ts` | `boundSectionText` 入段前调 `augmentResolvedPrompt`；留痕 `charCount` 用增强值；空集逐字节不变 | S-4、FR-3/4/8 |
| `packages/web/dsh-pmboard/src/application/gate/handlers/h3-inject.ts` | ① `ctx.verdict` 分流（negative/undefined → `skip(negative_verdict)`，不取词/不写 scratch/不留痕）；② 肯定分支取词后 augment | S-6、FR-3/10 |
| `packages/web/dsh-pmboard/src/application/gate/handlers/h4-resume.ts` | 非肯定分支**不附任何纪律块**（只摘要 + 用户意见）；肯定分支不变 | FR-10 |
| `packages/web/dsh-pmboard/src/application/internal/node-input-package.ts` | 追加「## 本节点文档（模板地址 · 先读再动手）」小节（位于「## 需求文档」之后，空集不追加） | S-7、FR-5/8/12 |
| `packages/web/dsh-pmboard/src/application/use-cases/IsolateNodeContext.ts` | 向 `buildNodeInputPackage` 传 `templateRoot` 与当前任务 | S-7、FR-12 |
| `packages/web/dsh-pmboard/src/adapters/CaptureHook.ts` | 绑定窗口 `onStagePrompt` 注入前 augment（第四处注入点） | FR-12 |
| `packages/web/dsh-pmboard/src/gate-wiring.ts` | 向链与捕获段传 `templateRoot` | FR-3 |
| `packages/web/dsh-pmboard/src/index.ts` | `PluginConfig` 加 `templateRoot?`/`addressSectionEnabled?`；解析并装配模板根 | FR-3 |
| `packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts` | 目标产物已确认（或计划已批准）→ 不弹框、返回既有字段 + `note`（守卫，无新输出字段） | FR-9/11 |
| `packages/web/dsh-pmboard/src/domain/prompt/fragments/common/iron-rules.md` | 增三条确认纪律（先答后确认 / 文字确认走 evidence / 同产物不重复弹框） | FR-9/11 |
| `packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts` | 由生成器重写（**不手改**） | 构建物 |
| `packages/web/dsh-pmboard/tests/fixtures/stage-prompts-baseline-p1.json` | 重跑 `dump-stage-prompts.mjs` 更新 P1 基线 | 兼容基线 |
| `docs/requirements/REQ-260922213356-4a45/design/architecture.md` | 校准落点与「同源」实现说明（表成员判定 + 守护单测，取代运行时 import 门禁规则） | FR-6/7 |

### 删除

| 项 | 结论 |
|---|---|
| `scripts/inline-templates.mjs` / `check-templates.mjs` | **从未实现**（requirement v16 已砍），无文件可删、无需回滚。本次仍不实现——防死链/防漏配由 T-1 守护单测覆盖 |

## 设计偏差与实现决策（须人可见）

- **D-0 计划 key 用大写 `T-1`~`T-8`**：`taskRefsFromDecomposition` 的任务编号识别式为
  `(?:T|BE|FE|TC|E)-\d+|t-[0-9a-f]{6}`，模板示例的小写 `t1` **不被识别** → 覆盖门禁读不到 RTM 绑定。
  故本计划用大写 `T-n`（仍满足 `reqboard_decompose` 的 key 集合一致性校验）。
- **D-1 门禁同源改为「表成员判定 + 守护单测」**：`stageEnabledFor`（shared/protocol）与
  `effectiveDesignDocs`（application/internal）都不在 domain 允许的依赖方向内（`tests/layer-boundary.test.ts`）。
  故 `resolveNodeTemplates` **不运行时 import 门禁规则**，改为：① 表只登记「门禁启用」的节点×类型组合
  （禁用组合无表项 → 自然返回 `[]`，等价于 `stageEnabledFor=false`）；② 守护单测断言
  「表 ⊆ 门禁 ∧ 门禁 ⊆ 表」与「禁用组合不得有表项」。同源由**机械断言**保证（与 data-model.md
  `chk_parity_with_gate` 的定义一致），domain 层保持纯函数与零越界依赖。
- **D-2 条件必交设计模板（frontend.md / backend.md）本期不进地址表**：requirement FR-2 的测试自检
  明确「feature design 给 5 份且不含迁移」，TC-1 也断言 5 条；`sides` 只存在于 requirement.md
  front-matter，三处注入点中系统段是**同步**路径读不到它，强行分侧会让三处地址段不一致（违反 TC-9）。
  故本期 design(feature) = 5 条必交；`design/frontend.md`/`design/backend.md` 进漏配检测的
  **显式 allowlist（带理由）**。后续若要分侧，扩展 `resolveNodeTemplates(stage, category, sides?)` 并同步三处。
- **D-3 上游必读用 domain 局部结构类型**：`resolveUpstreamDocs` 的入参用 `UpstreamSource { artifacts?, cardDoc? }`
  结构子集，不 import `shared/protocol.ts`（保持 domain 层边界）；调用方传真实 `RequirementRecord` 即可（结构兼容）。
- **D-4 模板根解析**：组合根按**自身模块位置**解析包根 `../templates`——源码态 `src/index.ts` 与构建态
  `dist/index.mjs` 同解为 `<pkg>/templates`（RISK-1：绝对路径，read 可打开）；配置 `templateRoot` 可覆盖。
- **D-5 发布边界**：`templates/` 不在 package.json `files` 里，但本 profile 是**指向仓库源码的软链**，
  磁盘上 `<pkg>/templates` 恒在；npm 发布场景不在本需求范围（如实记录，不加迁移卡）。

## 任务表

| 计划 key | 任务 id | 标题 | 需求条款 | 落点（编号+文件） | 阶段 | 端侧 | 依赖 | 工作量 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| T-1 | T-1 | 定义模板地址映射表与守护单测 | FR-1, FR-7 | T-1/T-3 + `packages/web/dsh-pmboard/src/domain/template/registry.ts`、`packages/web/dsh-pmboard/tests/template-address.test.ts` | implement | backend | — | M | `npx vitest run tests/template-address.test.ts` 全绿；临时移走 `templates/design/architecture.md` → 该测试变红（exit≠0）；`pnpm typecheck` 绿 |
| T-2 | T-2 | 实现地址解析与渲染纯函数 | FR-2, FR-3, FR-4, FR-5, FR-13 | I-1~I-4 + `packages/web/dsh-pmboard/src/domain/template/resolve.ts`、`packages/web/dsh-pmboard/src/domain/template/render.ts`、`packages/web/dsh-pmboard/src/application/internal/injection-address.ts` | implement | backend | T-1 | M | `npx vitest run tests/template-address.test.ts` 绿；空集 `renderAddressSection(...) === ''` 且 `augmentResolvedPrompt` `toBe(resolved)`（引用相等）；渲染出的每条路径被 `read` 实读成功（非空）；把 `templateRoot` 改成仓库根相对 `'templates'` → TC-12 变红 |
| T-3 | T-3 | 接线四个注入点并解析模板根 | FR-3, FR-4, FR-8 | S-4/S-5 + `packages/web/dsh-pmboard/src/adapters/TemplateRoot.ts`、`packages/web/dsh-pmboard/src/application/internal/capture-section.ts`、`packages/web/dsh-pmboard/src/application/gate/handlers/h3-inject.ts`、`packages/web/dsh-pmboard/src/adapters/CaptureHook.ts`、`packages/web/dsh-pmboard/src/index.ts`、`packages/web/dsh-pmboard/src/gate-wiring.ts` | implement | backend | T-2 | M | `npx vitest run tests/template-address-injection.test.ts -t 'TC-9'` 绿（三/四处地址段逐字一致）；`npx vitest run tests/prompt-injection-log.test.ts` 绿且 `charCount` 含地址段；`pnpm typecheck` 绿 |
| T-4 | T-4 | 实现非肯定项分流（H3 verdict / H4 不附纪律） | FR-10 | I-5/S-6 + `packages/web/dsh-pmboard/src/application/gate/handlers/h3-inject.ts`、`packages/web/dsh-pmboard/src/application/gate/handlers/h4-resume.ts`、`packages/web/dsh-pmboard/tests/template-address-injection.test.ts` | implement | backend | T-3 | M | `npx vitest run tests/template-address-injection.test.ts -t 'TC-10'` + `npx vitest run tests/h3-inject.test.ts` 绿；`verdict=negative/undefined` 时 `scratch.promptText` 未写、H4 文本不含下一节点纪律特征串；`affirmative` 输出与改造前逐字一致 |
| T-5 | T-5 | 补节点输入包地址节并锁两路径一致 | FR-8, FR-12 | S-7/UC-3 + `packages/web/dsh-pmboard/src/application/internal/node-input-package.ts`、`packages/web/dsh-pmboard/src/application/use-cases/IsolateNodeContext.ts`、`packages/web/dsh-pmboard/tests/template-address-injection.test.ts` | implement | backend | T-4 | M | `npx vitest run tests/template-address-injection.test.ts -t 'TC-11'` 绿；压缩开/关两路径地址段逐字一致且输入包含「## 本节点文档」；故障注入「地址只挂 H3、不挂输入包」→ 该测试变红 |
| T-6 | T-6 | 补空集兼容回归与回退开关 | FR-4 | I-3/I-4 + `packages/web/dsh-pmboard/tests/template-address.test.ts` | implement | backend | T-5 | S | `npx vitest run tests/template-address.test.ts tests/prompt-baseline.test.ts tests/stage-prompts.test.ts` 全绿；空集场景 sha256 与改造前一致；`addressSectionEnabled=false` 时注入文本与空集逐字节相同 |
| T-7 | T-7 | 增三条确认纪律并加同产物防重弹守卫 | FR-9, FR-11 | UC-4 + `packages/web/dsh-pmboard/src/domain/prompt/fragments/common/iron-rules.md`、`packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts`、`packages/web/dsh-pmboard/scripts/inline-prompt-fragments.mjs`、`packages/web/dsh-pmboard/scripts/dump-stage-prompts.mjs`、`packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts`、`packages/web/dsh-pmboard/tests/ask-confirm.test.ts` | implement | backend | T-1 | M | `node scripts/check-prompt-fragments.mjs` 退出 0；`npx vitest run tests/ask-confirm.test.ts` 绿；iron-rules 文本含三条纪律；对已确认产物再次 `reqboard_ask_confirm` → 弹框端口调用 0 次且返回体含「已确认」 |
| T-8 | T-8 | 加矩阵对照断言并校准设计落点 | FR-6 | T-1/T-3 + `docs/requirements/REQ-260922213356-4a45/design/architecture.md`、`packages/web/dsh-pmboard/tests/template-address.test.ts` | test | backend | T-1 | S | `npx vitest run tests/template-address.test.ts -t '矩阵'` 绿；故意改矩阵一格（如给 `(design, bug)` 塞条目）→ 断言变红；设计文档落点与代码路径逐条一致 |

## RTM 绑定（任务 ↔ 需求条款）

> 覆盖门禁的事实源：每行**一条**条款，逐条给出接收任务（一行多条款只会被识别首个，故此处一值一行）。

| 任务 id | 需求条款 | 落点摘要 |
|---|---|---|
| T-1 | FR-1 | 地址映射表 + 守护单测（路径存在/同源/漏配） |
| T-1 | FR-7 | 表 <> 门禁文档集双向一致（由守护单测断言） |
| T-2 | FR-2 | `resolveNodeTemplates(stage, category)` |
| T-2 | FR-3 | `renderAddressSection` / `augmentResolvedPrompt` 同批折入 |
| T-2 | FR-4 | 空集返空串 / augment 返原引用 |
| T-2 | FR-5 | `resolveUpstreamDocs` 上游必读 |
| T-2 | FR-13 | 指针行（名 + 用途 + 绝对地址），正文不内联 |
| T-3 | FR-3 | 四个注入点共用同一纯函数（接线） |
| T-3 | FR-4 | 空集时注入文本逐字节不变（接线） |
| T-4 | FR-10 | H3 verdict 分流 + H4 非肯定不附纪律 |
| T-5 | FR-8 | 压缩两路径地址一致 + charCount 记账 |
| T-5 | FR-12 | 压缩后再注入（输入包 + 每回合系统段） |
| T-6 | FR-4 | 空集兼容回归 + `addressSectionEnabled=false` 回退 |
| T-7 | FR-9 | 三条纪律 + 同产物防重弹守卫 |
| T-7 | FR-11 | 对话优先人机回路（弹框只留闸门一次） |
| T-8 | FR-6 | 节点×类型矩阵对照单测 + 设计落点校准 |

## 覆盖对照

| 需求条款 | 接口（interfaces） | 模块（backend/data-model） | 测试用例（test-cases） | 接收任务 | 完整性 |
|---|---|---|---|---|---|
| FR-1 映射集中一处 | —（纯常量；同源由单测断言） | T-1/T-3（data-model 实体） | TC-4, TC-5, TC-6（3） | T-1（1） | ✅ |
| FR-2 按节点/类型给地址 | I-1 | S-1 | TC-1, TC-2, TC-3, TC-12（4） | T-2（1） | ✅ |
| FR-3 与纪律同批送达 | I-3, I-4 | S-3, S-4 | TC-9（1） | T-2, T-3（2） | ✅ |
| FR-4 空集不扰动 | I-3, I-4 | S-4 | TC-8, TC-13（2） | T-2, T-3, T-6（3） | ✅ |
| FR-5 实施前上游必读 | I-2 | S-2 | TC-7（1） | T-2（1） | ✅ |
| FR-6 流程图与代码一致 | —（文档-代码矩阵对照，无运行时接口） | 守护单测（T-1 表） | TC-4, TC-6（2） | T-8（1） | ✅ |
| FR-7 与门禁同源 | I-1 | T-1/T-3 | TC-5（1） | T-1（1） | ✅ |
| FR-8 压缩后不丢且记账 | I-4 | S-4, S-7 | TC-11（1） | T-3, T-5（2） | ✅ |
| FR-9 先答后确认 | —（纪律文案 + 弹框守卫，无新增进程内接口） | AskConfirm 守卫 | TC-14（1） | T-7（1） | ✅ |
| FR-10 需修改不推着走 | I-5 | S-6 | TC-10（1） | T-4（1） | ✅ |
| FR-11 对话优先人机回路 | —（纪律文案 + 触发守卫） | AskConfirm 守卫 | TC-14（1） | T-7（1） | ✅ |
| FR-12 压缩后再注入 | I-4 | S-7 | TC-11（1） | T-5（1） | ✅ |
| FR-13 skill 式指针 | I-3 | S-3 | TC-9（1） | T-2（1） | ✅ |
| **合计** | 5 接口 | 7 函数/改动点 + 3 实体 | 14 用例 | 8 任务 | 13/13 条款有主 |

> FR-9/FR-11 有部分验收是**半自动**（TC-14 标注 ⚠️：措辞与真实弹框通道需人工确认），
> 计划中以「同一产物不重复弹框守卫」的可自动化断言（弹框端口调用计数 = 0）作为机械落点，
> 措辞部分由 T-7 的文本断言 + 人工复核覆盖。

## 风险与注意

| 风险 | 缓解（落在哪张卡） |
|---|---|
| RISK-1 地址相对仓库根 → read 打不开 | T-2 的「真 read 成功」断言 + 故障注入（相对根必红） |
| RISK-2 地址只挂 H3，压缩后静默丢失 | T-5 的压缩两路径一致性断言 + 故障注入 |
| RISK-3 表与门禁漂移 | T-1 的双向同源断言 + T-8 矩阵对照 |
| RISK-4 确认门又变「一直弹框」 | T-7 守卫 + 纪律三条 |
| RISK-5 改动面冲突（并行卡同文件） | 任务表依赖已把同文件卡串行（T-1→T-2→T-3→T-4→T-5→T-6；T-7/T-8 仅依赖 T-1/T-6） |
| 生成物不同步（改了 fragments 忘重跑生成器） | T-7 强制跑 `check-prompt-fragments.mjs`（退出 0 才算过） |

## 覆盖完整性规则

1. 每个 FR-1~FR-13 至少被一张任务卡接收（见上表「接收任务」列，13/13 有主）。
2. 设计文档里出现、却无人接收的编号 = 超范围设计 → 删掉或回需求补条款；本计划已逐项对照。
3. 事实源：本表「需求条款」列即 RTM 绑定，`reqboard_decompose` 的覆盖门禁据此判定
   （D-0：任务编号用 `T-n` 形态以通过编号识别式）。
