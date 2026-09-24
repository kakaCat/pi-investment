---
requirement_refs: [FR-2, FR-3, FR-4, FR-5, FR-9, FR-11]
---

# 接口设计（REQ-260922213356-4a45）

> 读者：实现本需求的 agent/开发。本需求**没有 HTTP 接口**——全部是进程内函数契约，
> 但契约与线上接口同等刚性：输入/输出/错误语义写死，实现不得自行发挥。
> 编号 I-x 供 test-cases「被测对象」引用。

## 接口清单 <!-- serves: FR-2, FR-3, FR-5 -->

| 编号 | 签名 | 用途（谁调用 + 做什么） | 输入 | 输出 | serves |
|---|---|---|---|---|---|
| I-1 | `resolveNodeTemplates(stage, category)` | 三个注入点调用，取「本节点该产出的模板条目」 | stage (PromptStage, 必填), category (Category \| undefined, 必填) | `readonly TemplateRef[]`（空数组 = 无模板） | FR-2, FR-7 |
| I-2 | `resolveUpstreamDocs(requirement, stage, currentTask?)` | 注入点调用，取「开工前该先读的上游产物地址」 | requirement (RequirementRecord \| undefined), stage (PromptStage), currentTask? (TaskRecord) | `readonly DocRef[]`（空数组 = 无上游） | FR-5 |
| I-3 | `renderAddressSection(input)` | 装配点调用，把两张清单渲染成地址段文本 | `AddressSectionInput`（见 §接口详细定义） | `string`（空集 = **空串**，非空白噪音） | FR-3, FR-4, FR-13 |
| I-4 | `augmentResolvedPrompt(resolved, input)` | 三个注入点共用，把地址段折进 `ResolvedPrompt` | resolved (ResolvedPrompt), input (AddressSectionInput) | `ResolvedPrompt`（空集 = 输入原样返回） | FR-3, FR-4, FR-8 |
| I-5 | `resolveStagePromptForGate(ctx, requirement, deps)` | H3 调用，按 verdict 决定「取词 or 跳过」 | ctx (ConfirmContext，含 `verdict`), requirement (RequirementRecord) | `{kind:'inject', text}` \| `{kind:'skip', code:'negative_verdict'}` | FR-10 |

## 接口详细定义 <!-- serves: FR-2, FR-3, FR-4, FR-5 -->

### I-1 resolveNodeTemplates <!-- serves: FR-2, FR-7 -->

**输入**
- `stage: PromptStage`（枚举：`brainstorming | design | decomposing | implementing | accepting | archived`）
- `category: Category | undefined`（枚举：`feature | bug | doc | refactor | spike | chore`）

**输出**：`readonly TemplateRef[]`；命中顺序 = 表中声明顺序（稳定，便于逐字断言）。

**语义**
1. 节点未启用（`stageEnabledFor(category, stage) === false`）→ 返回 `[]`（不注入，不是错误）；
2. 该类型在该节点无模板（如 bug 的 design）→ 返回 `[]`（**不臆造**）；
3. 条目按「模板内容」而非「文件维度」取——同一 `relPath` 可被多类型复用（如 architecture 用于 feature 与 refactor）。

**边界**
- `category` 未标（undefined）→ 按缺省 feature 处理（与 `DEFAULT_CATEGORY` 一致）；
- `stage` 为 `draft/done/canceled`（非可注入节点）→ 调用方不应到达；若到达返回 `[]`。

### I-2 resolveUpstreamDocs <!-- serves: FR-5 -->

**输入**
- `requirement: RequirementRecord | undefined`（undefined = 窗口无归属需求）
- `stage: PromptStage`
- `currentTask?: TaskRecord`（实施节点才有）

**输出**：`readonly DocRef[]`，只含**台账里确实存在**的产物。

**语义**
- 只从 `requirement.artifacts`（已登记产物）与 `currentTask.cardDoc`（任务卡文档路径）取；
- 取不到 → 不列出该项（**禁止臆造**）；
- 顺序固定：先上游节点产物（按节点顺序），再当前任务卡与其引用的设计文档；
- 文本里必须带纪律句「先读再动手」（由 I-3 统一渲染，不在本函数内拼文案）。

### I-3 renderAddressSection <!-- serves: FR-3, FR-4, FR-13 -->

**输入** `AddressSectionInput`：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `stage` | PromptStage | 是 | 当前节点 |
| `category` | Category \| undefined | 是 | 立项类型 |
| `requirement` | RequirementRecord \| undefined | 是 | 用于取上游地址 |
| `currentTask` | TaskRecord \| undefined | 否 | 实施节点当前任务卡 |
| `templateRoot` | string | 是 | **绝对路径**模板根（组合根注入；不由 domain 读环境变量） |

**输出**：`string`。**空集（两张清单都空）→ 返回 `''`**，调用方不得补任何空白/表头。

**渲染契约**（逐字，锁定单测）
```
## 本节点文档（模板地址 · 先读再动手）

产出模板（绝对地址，用 read 直接打开照写）：
- {title}：{templateRoot}/{relPath} —— {purpose}
...（每条一行）

上游必读（先读再动手）：
- {docKindLabel}：{docPath}
...（每条一行）
```
- 只有模板清单非空时输出第一块；只有上游清单非空时输出第二块；两块都空 → 返回空串。
- 指针行 = `人读名 + 一句话用途 + 绝对地址`；**正文不内联**（FR-13，成本恒定）。
- 上游地址用**工作区相对路径**（台账产物路径的既有口径，read 可打开）。

### I-4 augmentResolvedPrompt <!-- serves: FR-3, FR-4, FR-8 -->

**输入**：`resolved: ResolvedPrompt`、`input: AddressSectionInput`。

**输出**：新的 `ResolvedPrompt`：
- 地址段为空 → **返回入参 resolved 本身**（引用相等，保证 FR-4 逐字节兼容）；
- 地址段非空 → `{ ...resolved, text: resolved.text + '\n\n' + section, charCount: resolved.text.length + section.length + 2 }`；
- `fragmentIds / routeKey / hitLevel / trimmed` **保持不变**（地址段不是分片，不参与预算裁剪与回退链）。

**约束**
- 三处注入点**必须**调本函数，禁止各写一份拼接；
- 留痕（`injectionLog.record`）使用本函数返回值的 `charCount`（FR-8 记账含地址段）。

### I-5 resolveStagePromptForGate <!-- serves: FR-10 -->

**输入**：`ctx`（`ConfirmContext`，含 H1 回填的 `verdict: 'affirmative' | 'negative'` 与 `to`）、`requirement`。

**输出**：
- `verdict === 'affirmative'` → `{ kind: 'inject', text }`（沿用 `resolveStagePrompt` 取词结果）；
- `verdict === 'negative'` → `{ kind: 'skip', code: 'negative_verdict', reason }`——**不取词、不写 scratch.promptText、不留痕**。

**约束**：肯定分支行为与改造前逐字一致（防"修反"）；非肯定分支不得附带 `ctx.to` 的任何纪律文本。

### 数据契约（返回结构） <!-- serves: FR-2, FR-5, FR-13 -->

```ts
interface TemplateRef {
  id: string        // 稳定键，如 'design/architecture'（唯一，单测判重）
  stage: string     // 与 StagePromptKey 逐字一致
  category: string  // '*' = 该节点通用；或具体类型
  relPath: string   // 相对 templateRoot，如 'design/architecture.md'；不含 '..'
  title: string     // 人读名（架构设计 / 接口设计 …）
  purpose: string   // 一句话用途（进指针行）
}

interface DocRef {
  kind: string      // 产物 kind，如 'requirement' | 'design' | 'plan' | 'task'
  path: string      // 工作区相对路径
  title: string     // 人读名（需求说明 / 拆分计划 / 当前任务卡 …）
}
```

字段约束见 data-model.md §表/实体（T-1 / T-2）。

## 鉴权策略 <!-- serves: FR-2 -->

**不适用**（进程内纯函数，无网络边界）。三点说明：
- 调用方是三个注入点（同进程），不存在跨端调用；
- 上游地址只从**本窗口绑定需求**的台账读取，越权面在既有 reqboard 工具层，不在本段；
- 地址段不含任何凭证/持仓/账户信息，泄露面 = 模板文件的磁盘路径。

## 错误码规范 <!-- serves: FR-4 -->

本模块**不抛业务错误**（纯函数 + 空集语义）；以下为调用方必须遵守的降级口径：

| 情况 | 返回/行为 | 是否错误 | 说明 |
|---|---|---|---|
| 节点未启用 / 类型无模板 | `[]` → 空串 | 否 | 合法态；注入文本与改造前逐字节一致（FR-4） |
| 上游产物未登记 | 该项不列出 | 否 | 禁止臆造地址 |
| `templateRoot` 缺失（配置未给且包根解析失败） | 地址段整体不注入 + **响亮留痕**（`address_section_disabled`） | 是（可观测） | 不静默；FR-4 兼容仍成立 |
| 映射表 relPath 指向不存在文件 | 运行时不报错（空集不兜底）；**守护单测红** | 是（开发期） | 用红灯替代运行时兜底 |
| 渲染内部异常 | 由调用方降级（沿用既有注入降级留痕） | 是 | 不静默；H3 就地降级为 `degraded` |

## 接口版本管理 <!-- serves: FR-4 -->

- **接口形态**：进程内函数，随插件版本走（无 URL/Header 版本位）。
- **兼容承诺**：唯一对外可观察契约是**注入文本**——空集恒等（FR-4）承诺"没有地址可给时，改造前后逐字节一致"。
- **破坏性变更定义**：指针行文案格式变化（会打破"逐字断言"）→ 必须**同一提交内**更新守护单测与 test-cases 的期望串。
- **废弃策略**：若未来改为模板全文注入（非目标 N1），旧的 `renderAddressSection` 需保留一个版本并由测试覆盖回退路径。
- **回退开关**：`addressSectionEnabled=false`（配置）→ 立即回到改造前行为，无需回滚代码。
