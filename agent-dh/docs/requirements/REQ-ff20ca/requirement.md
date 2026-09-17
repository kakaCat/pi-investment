# REQ-ff20ca pmboard 文档预览接入官方右侧栏（sidebarRight）

> 状态：**定稿**（1–5 节经用户逐节确认）
> 类型：feature（优化插件）
> 绑定窗口：w-24ded829
> 上游设计：[REQ-31e11f requirement.md](../REQ-31e11f/requirement.md)（人机回路设计源）
> 纪律：分节撰写、逐节确认；未确认内容不写入本文。

## 1. 背景：设计的人机回路未被支撑

### 1.1 设计依据（REQ-31e11f 第 84–99 行）

用户在 REQ-31e11f 中定义的人机回路：

```
产物登记 → 飞书通知请人审阅
  → 人看文档 → 对话交流改进 → agent 修订产物 → 人在看板一键确认
  → 才放行对应转移（未确认代码级拒绝：artifact_not_confirmed）
```

并明确「**确认入口外置**：批准/确认按钮必须在需求卡面直接可达，不埋在详情抽屉里」。

**归属**：REQ-31e11f 第 159 行把「人机回路工程（reqboard_notify_human 多渠道通知 + 飞书卡片动作按钮）」明确列为 **out of scope、另立需求**——本次 REQ-ff20ca 即承接该工程。

### 1.2 问题一：UI 载体破坏回路（弹窗是模态遮挡）

回路第一环是「**人看文档 → 对话交流改进**」，这要求**边看文档、边与 agent 对话**。

而当前实现是**模态弹窗**：打开时盖住对话区、看完即关——人在看文档的那一刻恰恰无法对话，**回路起始环节直接断裂**，后续"agent 修订 → 人确认"无从谈起。

设计文档内部亦存在矛盾：第 94–97 行要求并排回路，第 127 行却写「弹窗展示」（实现选择与自身回路设计冲突）。

**结论**：`sidebarRight`（文档常驻右栏、对话区始终可见）才是该回路的合格载体。

### 1.3 问题二：agent 侧未工具化（没有让 agent 走回路的方式）

用户原话：「这个插件没有让你走人机回路的方式，这个也是要优化的」，并明确手段：**使用 `ask_user_question` 工具**。

现状核查（`src/host/stage-prompts.ts` brainstorming 段）：

| 现有纪律 | 是否工具化 |
|---|---|
| "一次一个问题" | ❌ 只写"每轮只问一个关键问题"——纯文风要求，未要求调用工具 |
| "分节逐段确认" | ❌ 只写"请用户确认或修改"——agent 可在回复里自说自话，不产生工具事件 |
| "HARD-GATE" | ⚠️ 代码级拦截（artifact_not_confirmed），但只在**推进时**兜底，平时不发问 |

缺口：**阶段纪律没有任何一句要求 agent 用 `ask_user_question` 发起回路**。因此问题与确认只是"聊天内容"：不可追踪、不可审计、agent 容易跳过。

**实证**：2026-09-16 本需求立项过程中，agent 未做任何需求提问、未分节确认、直接写完需求与计划并试图推进 planning——正是"回路未被工具化"的结果。

### 1.4 次要证据（支撑「走官方 sidebarRight」的决策）

| 问题 | 证据 |
|---|---|
| 自研渲染链路出过事故 | 2026-09-16 wrap 污染：`wrap-client.mjs` 逐行注入 \t\t 破坏 marked 多行模板字符串 → 弹窗 markdown 错乱 |
| 重复造轮子 | DSH 官方已有 `sidebarRight` + `documentpreview`，支持 Markdown/代码/图片/PDF/HTML |
| 两套弹窗并存 | 会话框一套（`doc-modal.ts`）、看板一套（`board-mount.ts:503`，带硬编码 `md·19:15`），后者样式已随清理丢失 |


## 2. 目标与范围

### 2.1 目标：让人机回路可以真正运转（两条腿）

回路的每一环都要有载体——本次补齐**载体侧（UI）**与**发起侧（agent）**两处：

| # | 目标 | 解决 1.x |
|---|---|---|
| **G1** | 文档打开统一走官方 `sidebarRight` + `documentpreview`（会话框 + 看板两处入口）——让「人看文档」与「对话交流」可**并行** | 1.2 |
| **G2** | 自研弹窗**完全删除**（会话框与看板两套实现），**不留降级分支** | 1.2 / 1.4 |
| **G3** | 阶段纪律**工具化**：明确要求 agent 用 `ask_user_question` 工具发起问题与确认——回路可追踪、不可跳过 | 1.3 |

### 2.2 改动清单

**改（入口接线）**

| 文件 | 改动 |
|---|---|
| `client/conversation-progress.ts` | `data-action="open-doc"` 点击 → sidebarRight（替换 `openDocModal`） |
| `client/board-mount.ts` | 文档点击 → sidebarRight（替换旧弹窗） |

**删（弹窗全套）**

| 对象 | 说明 |
|---|---|
| `client/doc-modal.ts` | 整个文件 |
| `client/board-mount.ts` 旧弹窗段 | 含硬编码 `md·19:15` 与 `dsh-pm-doc-modal-*` 类名（第二套实现） |
| `client/styles.ts` 弹窗样式 | `.dsh-pm-doc-overlay` / `-modal` / `-head` / `-path` / `-close` / `-ver` / `-body` |

**增**

| 对象 | 说明 |
|---|---|
| 文件地址构造 | `dsh-resource://file/session/<sessionId>/<path>`（对齐官方 grammar） |
| `host/stage-prompts.ts` 工具化 | 各阶段纪律明确要求用 `ask_user_question` 发起问题与确认 |
| **requirement 产物登记入口**（见 5.0） | 补登记能力（工具或阶段推进时自动登记），修复"看板确认 400 死锁" |

### 2.3 明确不做（边界）

- **不保留**弹窗降级分支——sidebarRight 为唯一路径（用户明确：直接删除不使用）。
- **不删** `marked` 依赖与 `.dsh-pm-md` 样式——`view.ts:626 renderMarkdown` 仍用其渲染需求卡描述（非弹窗用途，2026-09-16 核实）。
- 不改 reqboard 状态机、门禁判定逻辑、文档内容来源与存储位置。
- **不做**回路后续环节的自动化（如确认后自动回执/续跑会话）——澄清时只指认「让 agent 知道该走回路（用 `ask_user_question`）」，未纳入闭环自动化；如需要另议。


## 3. 方案

### 3.1 G1：接入官方 `sidebarRight`

**调用链**

```
文档点击（会话框 / 看板）
  → sessionId = 槽位注入优先，回退「当前会话」快照
  → address  = dsh-resource://file/session/<sessionId>/<path>
  → ctx.sidebarRight.openResource(address)     // 官方右栏 + documentpreview 渲染
```

**3.1.1 地址构造**

**决定：本地实现 `client/file-address.ts`**（对齐官方 grammar，约 20 行 + 单测）。

理由：零新增依赖，不需要 `pnpm install`（规避依赖被替换为硬链接副本后静默过期的陷阱）；该 grammar 已冻结，可用单测锁定。代码内注明官方出处，上游如有变更则同步并补测试。

**3.1.2 sessionId 来源**（已核实）

| 入口 | 来源 |
|---|---|
| 会话框 | 槽位注入的 `sessionId`（`conversation-progress` 已有 `resolveSessionId`） |
| 看板 | 无会话上下文 → 会话服务快照「当前会话」`sessions.list.getSnapshot().current`（同 conversation-progress 兜底逻辑） |
| 都取不到 | 无法构造 session 地址 → 打印诊断（**无降级**，按 G2） |

**3.1.3 服务访问**

- `(ctx as any).sidebarRight` **可选访问**——**不得**加入 `export const inject`，否则服务缺失会导致整个 client 插件加载失败。
- 不可用时：console 明确诊断（不做降级）。

**3.1.4 删除清单**：见 2.2「删」（`doc-modal.ts` / `board-mount.ts` 旧弹窗段 / 弹窗样式）。

### 3.2 G3：阶段纪律工具化

**决定：在 `host/stage-prompts.ts` 各阶段纪律中增加明确条款**——问题与确认**必须用 `ask_user_question` 工具发起**，未获确认不得推进。

理由：一处常量表改动；确定性注入（与状态机同仓同版本）；可用单测锁定措辞防回退。—— 先落地这一层，观察实际效果；是否再加"门禁校验本阶段有无工具事件"的硬约束，视效果另议。

### 3.3 风险与验证

| 风险 | 验证 / 对策 |
|---|---|
| session workspace 根 ≠ 文档相对路径基准（`docs/...`） | **实施第一步实测**：13080 点一个文档，看右栏能否打开；不行则改传绝对路径或在 host 侧富化地址 |
| `ctx.sidebarRight` 未随实例加载 | **实施第一步探测**，console 打印诊断 |
| 删除弹窗后看板入口失效 | 同批替换；验收含看板入口实测 |

### 3.4 交付顺序

1. **确认门工具化（最高优先，见 5.1）**：让 `ask_user_question` 的确认具备落章效力——打通"会话确认 → 推进门"链路（当前被 `REQBOARD_HUMAN_GATE` 拒绝）
2. **最小验证**：接会话框一个入口 → 实测右栏能否打开（一次验证地址/session/服务三件事）
3. 验证通过 → 全量接线（看板）+ 删除弹窗全套
4. G3 阶段纪律提示词工具化（独立小改，可单测）
5. 文档更新


## 4. 验收标准

### 4.1 G1 + G2：UI 载体与弹窗删除

1. 会话框流程卡片点击文档 → **官方右侧栏**打开该文件；Markdown 正确渲染（列表续行**不出现** `<pre>` 代码块）。
2. 看板详情点击文档 → 同上（不再出现 `md·19:15` 弹窗）。
3. 同一文件重复点击 → 右栏**去重聚焦**，不产生重复 tab。
4. **回路第一环成立**：右栏打开时左侧对话区仍可见可用（可"边看文档边对话"）。
5. 弹窗全套已删：`doc-modal.ts` 文件不存在；`board-mount.ts` 无旧弹窗段；`styles.ts` 无 `.dsh-pm-doc-overlay` / `-modal` / `-head` / `-path` / `-close` / `-ver` / `-body`。
6. **无降级残留**：全仓 grep 无 `openDocModal` 引用；无"右栏不可用则弹窗"分支。

### 4.2 G3：agent 侧工具化

7. `host/stage-prompts.ts` 各阶段纪律含**必须用 `ask_user_question` 工具**发起问题与确认的明确条款；单测锁定该措辞（防回退）。
8. 阶段提示词注入机制未被破坏（既有注入点与单测仍通过）。

### 4.3 工程与边界

9. `file-address.ts` 单测覆盖：相对路径、`./` 前缀、反斜杠、含空格/中文路径、段编码与官方 grammar 一致。
10. 构建门禁通过：`pnpm build:client`（含 verify sentinel 哨兵检查）。
11. 看板入口实测：删除弹窗后文档点击不失效。
12. **边界核验**：`view.ts` 需求卡描述 markdown 仍正常渲染（`marked` 与 `.dsh-pm-md` 保留）；reqboard 状态机与门禁判定逻辑未被改动。

### 4.4 验收方式

- **实测**：13080 实例上完成 1/2/3/4/11（含右栏打开、去重、边看边聊）
- **单测**：`npx vitest run`（file-address、stage-prompts 新增用例）
- **静态核查**：5/6/9/12（grep + 文件存在性）
- **构建**：10

## 5. 确认门交互方式（第 4 节确认后的补充）

**决定：人工确认门采用双通道，以工具为主。**

| 通道 | 角色 | 说明 |
|---|---|---|
| **`ask_user_question`（主）** | agent 主动发起 | 每个门（需求文档确认 / 计划批准 / 拆分清单确认 / 验收 / 归档）agent **主动用工具**请人确认——把"请人去看板点"改为会话内工具提问，回路可追踪 |
| 看板一键按钮（保留） | 异步备选 | 人不在对话时仍可确认；满足 REQ-31e11f「确认入口外置、卡面直接可达」的既有设计 |

两通道语义一致（同一份台账的确认状态）。

**实现要点（待计划细化）**

1. 阶段纪律提示词必须写明：**到达门时必须用 `ask_user_question` 发起确认**（不只是"提问"，确认动作本身也走工具）。
2. 确认语义落章：现有门禁要求"人工闸门、agent 不可代替"——需评估如何与"用户已在会话中明确答复"衔接（可能需要新增按用户答复落确认的通道），**本需求不改变门禁的"必须有人确认"内核**，只增加发起方式与凭据形态。

**验收补充（追加至 4.2）**

- 9. agent 在需求文档完成/计划提交等门处，**用 `ask_user_question` 发起确认**（可观察的工具事件，而非仅在回复里说一句）。
- 10. 看板一键按钮仍能完成同一确认；两通道结果一致（台账确认状态相同）。
- 11. **凭据效力**：用户在会话中对 `ask_user_question` 的明确确认，与看板点击具有同等效力——agent 据此可推进对应门（当前被 `REQBOARD_HUMAN_GATE` 拒绝，本需求需打通）。

### 5.0 关联缺陷（现场发现，2026-09-16）：需求文档产物无登记入口

用户在看板点「确认产物」报 **400 Bad Request**，根因链路：

1. `handleArtifactConfirm` 要求产物**已登记**：`if (artifact === undefined) badInput("没有 kind=… 的产物（须先由工具登记）")`
2. 但 `registerArtifact` 只在 `reqboard_decompose` / `plan_submit` / `verify_submit` / `task_report` 中被调用
3. **brainstorming 阶段完成 requirement.md 后，没有任何工具或 HTTP 接口能登记它**（`req/move`、`req/artifact/confirm` 等均无登记能力）
4. → `artifacts` 为空 → 看板确认按钮 400 → 状态推不动 → **死锁**

**本需求需一并修复**：提供 requirement 产物的登记入口（或在阶段推进时自动登记），否则五道人工确认门的第一道永远无法通过。

### 5.1 优先级：本项最优先交付（2026-09-16 用户决定）

**"确认门工具化"排在所有 UI 项之前。**

理由（现场实证）：本需求立项过程中，用户已通过 `ask_user_question` 明确确认需求文档定稿，但 `reqboard_move(brainstorming→planning)` 仍被拒——
`REQBOARD_HUMAN_GATE：需人在项目看板点击确认，agent 不可代替`。
即**门禁不认会话确认凭据**，agent 无法用工具完成回路，流程本身被卡住。故必须先打通该链路，其余改动（sidebarRight 接线、弹窗删除）随后。
