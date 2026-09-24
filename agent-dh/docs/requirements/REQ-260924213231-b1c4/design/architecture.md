---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8]
---

# 架构设计（REQ-260924213231-b1c4 · 修 REQ 流水线设计阶段死锁）

> 读者：工程 / agent。根因与证据见 requirement.md §2；本文只讲「怎么改」。
> 所有代码坐标相对 `packages/web/dsh-pmboard/`（:13080 实际加载的插件）。

## TL;DR <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

三条主线：
1. **登记去旁路化**：把「扫描需求目录 → 登记产物」从只有 HTTP 渲染能触发的 `adapters/ArtifactSync.ts`，
   下沉为 application 层纯函数 + 工具用例（FR-1），并让 G2 闸门把「未登记」与「未落章」说成两句不同的话（FR-2）。
2. **弹框去阻塞化**：人在环确认改为「投递 + 回执」（非阻塞），调用方预算不再是失败判据（FR-3）。
3. **契约收口**：零参绑定等价 `{}`（FR-4）、设计阶段提示词写明登记命令（FR-5）、
   立项降级路径不丢文档位置（FR-7）+ pm 弹框来源标志（FR-8）；断点常驻台账并由输入包带出（FR-6）。

## 设计总览 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

```
  agent（run_code）        pmboard application           台账/磁盘
   │ tools.reqboard_submit   │                              │
   │  (kind=design) ───────► │ submitDesignArtifacts ──────►│ discoverArtifactsFrom(docs, req)
   │                         │ 幂等 registerArtifact        │   → req.artifacts（kind=design）
   │◄── design_docs 逐份态 ──│                              │
   │                         │                              │
   │ tools.reqboard_move ───►│ checkDesignCompletenessGate  │
   │   design→decomposing    │  未登记 / 未落章 两种文案     │
   │◄── 拒绝 + 唯一下一步 ───│                              │
   │                         │                              │
   │ tools.reqboard_ask_confirm ► questions.ask()（投递）    │
   │◄── 宽限内=confirmed ────│  超宽限=pending+ticket       │
   │                         │  └─(后台) 作答 → 落章+推进 ──►│ 落章写台账 + 唤醒窗口
   │ tools.reqboard_confirm_receipt(ticket) ────────────────►│ 读回执/台账 → confirmed=true
```

| 组件 | 职责（一句话） | 改动文件 |
|---|---|---|
| 产物发现核心（纯函数） | 由 `DocRepository` 端口列出需求目录并分类为产物的**唯一**实现 | 新增 `src/application/internal/artifact-discovery.ts` |
| ArtifactSync（适配器） | 改为一层薄壳：调核心 + 落库（行为不变，消除两份真相） | `src/adapters/ArtifactSync.ts` |
| 设计登记用例 | `kind=design` 的登记编排：幂等登记 + 逐份态投影 | 新增 `src/application/use-cases/SubmitDesignArtifacts.ts` |
| 提交工具 | `SUBMIT_KINDS` 增 `design`，分派表加一行；输出 schema 增字段 | `src/tools/SubmitTool/SubmitTool.ts` |
| 状态查询 | `reqboard_status` 增 `design_docs`（逐份：on_disk/registered/confirmed）与 `interruption` | `src/application/query/QueryState.ts`、`src/tools/StatusTool/StatusTool.ts`、`src/application/internal/design-docs.ts` |
| G2 闸门文案 | 按「未登记 / 待确认」分化 gap 文案并附**唯一**命令 | `src/application/internal/design-gates.ts` |
| 确认用例 | 已确认早返回补 `gate_failure`；新增宽限 + 挂起 + 后台落章 | `src/application/use-cases/AskConfirm.ts` |
| 挂起确认注册表 | 内存 `ticket → 状态`；回执与后台完成共用 | 新增 `src/adapters/PendingConfirmRegistry.ts` + `ports.ts` 端口 |
| 回执用例/工具 | 查询挂起确认的结果（幂等，落库为准） | 新增 `src/application/use-cases/ConfirmReceipt.ts`、`src/tools/ConfirmReceiptTool/` |
| 绑定层补丁 | 缺省参数 `{}`（零参工具可调） | 新增 `patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch` + 根 `package.json` |
| 设计提示词 | 写明登记命令与时机 | `src/domain/prompt/fragments/design/light/overrides.md`、`.../heavy/overrides.md` + 重生成 `generated/fragments.ts` |
| 断点记录 | 台账 `interruption` + 输入包新节 + 补写工具 | `src/shared/protocol.ts`、`src/application/internal/node-input-package.ts`、`src/tools/NoteInterruptionTool/` |
| 立项降级 | `reqboard_create` 增 `doc_location`，回落留痕，并推进到终态 | `src/tools/CreateTool/CreateTool.ts`、`src/application/use-cases/CreateRequirement.ts` |
| 弹框来源标志 | `pmHeader()` 统一注入 | 新增 `src/domain/text/pm-badge.ts` + `AskConfirm.ts`/`AcceptSheet.ts`/`capture-mapping.ts`/`HandleFailure.ts` |

## 根因 → 修点对照 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-6, FR-7 -->

| 根因（requirement §2.2） | 修点 | 结构性判据（可证伪） |
|---|---|---|
| 登记只挂 HTTP 渲染路径 | 新增 `kind=design` 工具入口 + 共享发现核心 | 不打开看板页面也能登记（A1） |
| 未登记 / 未落章同文案 | G2 gap 分化 + ask_confirm 早返回补缺口 | 两条消息文案不同且各带命令（A2） |
| 弹框 1h vs 调用方 120s | 投递 + 回执（非阻塞） | 发起调用不再产生 deadline 失败（A3） |
| 零参被绑定层拒 | 运行时绑定缺省 `{}` | `tools.reqboard_status()` 正常返回（A4） |
| 降级路径丢第四问 | `reqboard_create` 增 `doc_location` + defaults 留痕 | 不传=显式回落留痕；传则路径生效（A5/FR-7） |
| 中断后无断点 | 台账 `interruption` + 输入包「断点」节 | 注入 TIMEOUT 后续跑含断点章（FR-6） |

## 数据流（含失败分支） <!-- serves: FR-1, FR-2, FR-3, FR-6 -->

```
调用方(run_code)   SubmitTool      用例              文档端口        台账
  │ kind=design       │              │                 │             │
  │ ─────────────────►│ 校验 kind    │                 │             │
  │                   │ ────────────►│ list(design/) ─►│             │
  │                   │              │ ◄── 文件清单 ───│             │
  │                   │              │ 已存在路径 → 跳过（幂等）      │
  │                   │              │ ── mutate 登记新条目 ─────────►│
  │ ◄─ design_docs 逐份态 + 下一步命令（含失败：目录不存在→空集，不报错）│

调用方        AskConfirm         questions.ask        PendingConfirm  台账
  │ ─────────────►│ 投递问题          │                   │            │
  │               │ ─────────────────►│（宿主弹框）        │            │
  │  宽限内作答   │ ◄── answers ──────│                   │            │
  │ ◄─ confirmed=true，落章+推进 ───────────────────────────────────►│
  │  超宽限       │ 登记 ticket，立即返回 pending=true     │            │
  │ ◄─ pending+ticket（**不判失败**）                      │            │
  │               │ （后台）answers 到达 → 落章+推进+唤醒 ───────────►│
  │ reqboard_confirm_receipt(ticket) ─────────────────────►│ 读回执/台账 │
  │ ◄─ confirmed=true，advanced=true ────────────────────────────────│
```

失败分支：① 目录不存在 / 无 .md → 登记 0 条，返回「无设计文档可登记」，**不谎报成功**；
② 登记路径不可打开（伪路径/越界）→ 复用 `assertArtifactOpenable` 的 `REQBOARD_ARTIFACT_NOT_OPENABLE`；
③ 弹框通道不可用 → `fallback=board`（现有语义不变）；④ 回执过期/被丢弃 → 以台账 `confirmedAt` 为准（幂等，不猜）。

## 逐条功能点实现要点 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

| FR | 落地函数 / 文件 | 关键签名与语义 |
|---|---|---|
| FR-1 登记 | 新增 `application/internal/artifact-discovery.ts`：`discoverArtifactsFrom(docs, req): StageArtifact[]`；新增 `use-cases/SubmitDesignArtifacts.ts`：`submitDesignArtifacts(deps, args, exec)` | 纯函数按 `docs.list(需求目录/design)` 产出待登记条目（`kindForRelPath` 分类 + 已登记 path 跳过）；用例在**一次 `mutate`** 内 `registerArtifact` 全部条目，返回逐份态与 `registered_count` |
| FR-1 查询态 | 改 `application/internal/design-docs.ts`：`designDocRegistration(req, category, policy, onDisk)` | 合并三源：磁盘（`on_disk`）、产物簿（`registered`）、确认章（`confirmed`）；`QueryState` 输出 `design_docs` |
| FR-2 文案 | 改 `application/internal/design-gates.ts`：`checkDesignCompletenessGate` 的 `gaps` 构造；新增 `application/internal/gate-feedback.ts`：`envelope(f)` | 同一条目按 `art === undefined`（未登记）与 `confirmedAt === undefined`（待确认）**分叉**；**全部内容闸门**统一走三要素信封「what + why + how」（见下节） |
| FR-2 消矛盾 | 改 `use-cases/AskConfirm.ts` 的「已确认早返回」分支 | `alreadyConfirmed` 为真时先跑 G2；有缺口则返回 `gate_failure` + 「仍有 N 份未登记」，不再与 move 文案打架 |
| FR-3 弹框 | 改 `use-cases/AskConfirm.ts`；新增 `ports.ts` 的 `PendingConfirmPort`、`adapters/PendingConfirmRegistry.ts`、`use-cases/ConfirmReceipt.ts` | `questions.ask` 与宽限计时器**赛跑**：宽限内作答 = 旧语义；超宽限 = 登记 `ticket` 后立即返回，并在 `.then()` 里后台落章/推进/唤醒；回执按 ticket 查，缺 ticket 时回退读台账 `confirmedAt` |
| FR-4 绑定 | 新增 `patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch` | 绑定工厂 `value: (args) => …` 改为 `value: (args = {}) => …`（唯一改动） |
| FR-5 提示词 | 改 `domain/prompt/fragments/design/{light,heavy}/overrides.md`，重跑 `scripts/inline-prompt-fragments.mjs` | 覆盖条目 1 改写：登记命令 + 触发者 + 「不要猜 kind」；P1 基线重生成 |
| FR-6 断点 | 见下节「FR-6 断点留痕：实现细节」 | 常驻 checkpoint（自动）+ 事后补原因（事件/工具两入口）+ 输入包「断点」节 |
| FR-7 位置 | 改 `tools/CreateTool/CreateTool.ts` + `use-cases/CreateRequirement.ts` | 增 `doc_location` 入参 → `createRequirementDirect({ …docBasePath })`；返回补 `doc_location`/`defaults_used`；随后复用 `advanceDraftToBrainstorming`（从 `CaptureRequirement.ts` 提到 `internal/`）返回终态 |
| FR-8 标志 | 新增 `domain/text/pm-badge.ts`：`pmHeader(text): string` | 返回 `📋 PM · {text}`；四处构造点统一调用（`AskConfirm` / `AcceptSheet` / `capture-mapping` / `HandleFailure`） |

## FR-6 断点留痕：实现细节 <!-- serves: FR-6 -->

**为什么不是「探测到超时才写」**：回合被上游超时打断后，pmboard 已经没有任何机会执行代码——
所以断点必须在**死亡之前**就已存在，且能表达「当前阶段 + 未完成动作」。故设计为两层：
**常驻 checkpoint（自动、零探测）+ 事后补原因（事件驱动 + 工具兜底）**。

**已验证的宿主接缝**（读本地 DSH 包确认，不是猜测）：

| 事实 | 证据（本地 node_modules） |
|---|---|
| pmboard 的 `CaptureHook` 已订阅 `session/event`，并已处理 `turn/end` | `packages/web/dsh-pmboard/src/adapters/CaptureHook.ts:225-251` |
| `turn/end` 的 `data` = `{ turn, reason: TurnEndReason }` | `@deepseek-ai/dsh-session/lib/types/types.d.ts:260-263` |
| `reason.kind` 值域 = `completed` / `aborted` / `blocked` / `error`（带 `error: LlmFailure`）/ `max-tokens` / `interrupted` | 同上 `types.d.ts:165-199` |
| 崩溃孤儿回合由 agent-loop resume / 冷读合成 `{ kind: "interrupted" }` | `@deepseek-ai/dsh-session/lib/index.js` 的 `interruptedTurnClosers` |

**四个部件**：

1. `application/internal/interruption.ts`（纯逻辑，零 I/O；application 层禁 import node:）
   - `turnEndOutcome(data: unknown): { abnormal: boolean; reason: string } | undefined`
     `completed` → `{abnormal:false, reason:"completed"}`；`max-tokens` / `blocked` → 非 abnormal（可续，不算中断）；
     `aborted` → `{abnormal:true, reason:"aborted:" + cancelledBy}`；`interrupted` → `{abnormal:true, reason:"interrupted"}`；
     `error` → `{abnormal:true, reason:"error:" + (error.code ?? "") + ":" + error.message}`（**上游流超时落在这里**）。
     形态不认识（缺 `data`/`reason`）→ `undefined`（不猜、不误报）。
   - `nextActionFor(req: RequirementRecord): string`：按 `req.status` + 产物态给出**唯一**下一步命令
     （design 无产物→`reqboard_submit(kind=design)`；已登记未落章→`reqboard_ask_confirm(target=artifact, kind=design)`；
     decomposing→`reqboard_submit(kind=plan)`；implementing→`reqboard_task_run`；accepting→`reqboard_accept_sheet`；done→`reqboard_submit(kind=archive)`）。
   - `stampCheckpoint(req, now, tool)`：就地写 `req.interruption`（`reason="checkpoint"`）；**幂等**——
     `stage` 与 `pendingAction` 都未变时不写、不 bump `updatedAt`（避免每个工具都制造一次变更）。
   - `stampInterruption(req, now, reason, tool)`：显式覆盖 `reason`（保留 `pendingAction`）。
2. **写入器 A（自动，覆盖 100% 场景）**：每个交棒用例在 `mutate` 尾部调一次 `stampCheckpoint`
   （`ask_confirm` / `move` / `submit` / `decompose` / `task_move` / `accept_sheet` 各一行）。
   断点因此**永远等于「最后一步做完后的下一步」**——即使没有任何失败探测，断点也已存在。
3. **写入器 B（事后补原因，两个入口，任一可用即可）**：
   - 事件入口（自动）：`CaptureHookDeps` 增 `onTurnFinished?: (windowKey: string, outcome, session: unknown) => void`；
     `turn/end` 分支读 `evt.data` → `turnEndOutcome` → **只发信号**（沿用 D-17：监听器内不做会话写操作）。
     组合根 `src/index.ts` 把它接到**异步边界**（与 `node-settlement` 同一个 `schedule`/`setImmediate` 纪律），
     调 `noteInterruption` 写台账 + 一条 `[断点]` 评论；异常只 `logger.warn`，绝不冒泡打断流水线。
   - 工具入口（显式兜底）：`reqboard_note_interruption(reason)` → 新增 `use-cases/NoteInterruption.ts`
     （绑定窗口校验 + mutate + comment）。用于事件入口不可得（旧 DSH 版本 / 事件形态变化）或 agent 自己发现上一回合中断。
4. **输入包渲染**：`projectLedger` 增 `breakpoint` 投影；`buildNodeInputPackage` 在「未决问题」之后
   **条件追加** `## 断点` 节（仅当 `requirement.interruption` 存在），含：阶段 / 未完成动作 / 中断原因 / 时间。
   老需求无字段 → 不追加，输出与改造前逐字节一致（有回归测试）。

```
FR-6 数据流（两层写入）

  交棒工具成功 ──► stampCheckpoint ──► req.interruption = {reason:"checkpoint", stage, pendingAction}
                                              ▲（总是最新）
  回合结束 turn/end ──► CaptureHook 读 data.reason
      │                    │
      │ completed/max-tokens/blocked → 不补写（A 的 checkpoint 已覆盖）
      │ aborted / error / interrupted → 异步边界 → noteInterruption →
      │                                   req.interruption.reason = "error:…/aborted:…/interrupted"
      └ 形态不认识 → 不写、不报错（A 仍在）

  续跑：buildNodeInputPackage(req) ──► 追加「## 断点」节 ──► 新窗口据此续跑
```

**失败模式**：① 事件形态不认识 → 不写、不报错（A 的 checkpoint 仍在）；② 台账写失败 → `warn` + 下次 `status` 仍能读到旧断点；
③ 老需求无字段 → 输入包不追加该节；④ 同一回合多次 `turn/end` → 以 `at` 最大者为准（后写覆盖前写，单对象不累计）。

## 闸门拒绝信封（FR-2 扩展）：报错原因 + 补齐指引 <!-- serves: FR-2 -->

**反馈**：门禁拦下文档时，必须同时说清「**为什么被拦**」与「**怎么补齐**」——只给结论（「未确认」「未交」）
等于把排查成本整段转给 agent（REQ-2cd3 事故里 agent 只能盲试，正是这一点）。

**统一信封**（所有内容/形态闸门共用，唯一实现 `application/internal/gate-feedback.ts`）：

```
reqboard_<tool> 未执行：<what 哪份文档 / 哪一条> —— <why 报错原因>。补齐：<how 可复制的一步>
```

三要素缺一不可；`how` 必须是**可执行锚点**（`reqboard_*` 命令 / 模板路径 / 具体字段名），
不接受「请检查文档」这类无法照做的空话。

| 闸门 code | what | why（报错原因） | how（补齐指引） |
|---|---|---|---|
| `design_doc_incomplete`（未登记） | `design/use-cases.md` | 产物簿无此条 | `reqboard_submit(kind=design)` |
| `design_doc_incomplete`（待确认） | `design/use-cases.md` | 已登记但无确认章 | `reqboard_ask_confirm(target=artifact, kind=design)` |
| `design_orphan` | `architecture.md` → 章节「设计总览」 | 该二级章节缺 `serves` 标注 | 在标题行补 `serves: FR-#`（多值逗号分隔）；不服务任何条款的章节删掉或合并 |
| `dangling_reference` | `D-ARCH-2 → FR-9` | serves 指向的编号不存在 | 改成 requirement.md 里已存在的 `FR-#`，或删掉该引用 |
| `requirement_uncovered` | `FR-6` | 无任务卡接收、也未标「本轮不做」 | 给对应任务卡加 `requirement_refs=["FR-6"]`；确不做则在该条款旁写明「本轮不做」+ 理由 |
| `requirement_missing_clauses` / `requirement_clause_sequence_gap` / `requirement_clause_duplicates` | 缺失/跳号/重复的编号 | 根文档编号不满足规范 | 按 requirement.md 模板补齐 `FR-n` 连续且唯一 |
| `REQBOARD_MISSING_REQUIRED_DOC` | `design/frontend.md` | 该类型必交文档未交 | 按 `templates/design/*.md` 生成该份；不适用则在需求 front-matter 写 `design_exempt=frontend.md=理由` |
| `REQBOARD_ARTIFACT_NOT_OPENABLE` / `REQBOARD_FILE_MISSING` | `<path>` | 伪路径（brace/通配/越界）/ 文件不存在 | 先把文档落到工作区相对路径，再登记 |
| `design_contains_decomposition` | `architecture.md` → 「任务表表头（…第 N 行）」 | 设计文档混入拆分内容 | 把该表挪到 `decomposition.md`（拆分阶段产物）后重试 |
| `REQBOARD_EVIDENCE_FAKE` | `<evidence 片段>` | 未命中该窗口真实用户消息 | 引用用户原话；或改走弹框确认路径 |

**实现与边界**：判定逻辑**一律不动**（护栏强度不降，NFR-2）；只把 `GateFailure.message` 的拼接统一走 `envelope()`，
`GateFailure.gaps` 保留结构化明细（页面标红用）。`gap` 为空/形态不认识时**不伪造 why**，如实写「未分类缺口」并给通用下一步。

**零信任核对**：`tests/gate-feedback-envelope.test.ts` 对**每一个** `GateFailure.code` 断言
① 消息含 `——`（why 分隔）与 `补齐：`（how 分隔）；② `how` 段命中可执行锚点（`/reqboard_[a-z_]+/` 或 `templates/` 或 `design_exempt`）。
## 方案对比 <!-- serves: FR-1, FR-3, FR-6 -->

| 决策点 | 方案 | 结论 |
|---|---|---|
| FR-1 登记入口 | A：`reqboard_submit` 增 `kind=design`；B：新增 `reqboard_register_design` 工具 | ✅ A——登记本就是 submit 语义（产物已落盘→登记），复用分派表与提示词；避免工具数继续膨胀。B 的独立可发现性是唯一优势，可由提示词补足 |
| FR-1 实现层 | A：application 纯函数（走 `DocRepository` 端口）供适配器与用例共用；B：用例直接调 `ArtifactSync`（import 适配器） | ✅ A——分层门禁（layer-boundary）禁止 application import adapters；且消除「发现逻辑两份实现」 |
| FR-3 预算 | A：投递 + 回执（非阻塞）；B：把调用方预算默认值抬到 10 分钟；C：A（B 作可选） | ✅ A——唯一结构性解（不依赖调用方预算）；B 只是把悬崖从 2 分钟推到 10 分钟，30 分钟等待仍失败，故只作部署侧可选增强（见开放问题 OQ-1） |
| FR-6 断点落点 | A：需求台账 `req.interruption`；B：Session state 文件 | ✅ A——避免「两份真相」；输入包本就从台账投影，跨窗口/跨进程可读 |

## 四视角落点 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

| 视角 | 文档 | 本设计要点 |
|---|---|---|
| 架构 | 本篇 | 登记去旁路化；弹框去阻塞化；绑定层补丁的边界声明 |
| 接口 | use-cases.md + interfaces.md | 每个 FR 的入参/返回/错误码与兼容性 |
| 数据模型 | data-model.md | `interruption` 新字段、`design_docs` 投影、挂起确认（内存，非持久） |
| 测试策略 | test-cases.md | 单元 + 集成 + 故障注入 + E2E 复跑 |

## 研发规范 <!-- serves: FR-1, FR-3, FR-4, FR-5 -->

| 类别 | 规范 | 来源 | 本次如何遵守 |
|---|---|---|
| 分层 | application 不 import adapters/node:（layer-boundary 门禁） | `tests/layer-boundary.test.ts` | 发现核心走应用层纯函数，I/O 只在 adapters |
| 尺寸 | 单文件 ≤400 行 | `tests/size-budget.test.ts` | 新能力各自独立模块（design-gates 已因尺寸拆出） |
| 输出契约 | 工具返回键必须在输出 schema 声明 | `tests/output-contract.test.ts` | 新增字段一律同步 schema 与契约测试 |
| 提示词 | 分片是文本源，`generated/fragments.ts` 是产物 | `scripts/inline-prompt-fragments.mjs` | 改 .md 后重跑内联脚本 + 更新 P1 基线 |
| 依赖 | 修 DSH 行为走本仓 `pnpm.patchedDependencies` | 根 `package.json`（已有 2 个 patch 先例） | FR-4 只加一个最小 patch，不改上游仓库 |
| 留痕 | 闸门拒绝必带 code + 唯一下一步命令 | 本仓铁律 | FR-2 两种病因两种 code/文案，各带命令 |

## 错误处理 <!-- serves: FR-2, FR-3, FR-4, FR-7 -->

| 失败点 | 检测方式 | 处置 | 留痕 |
|---|---|---|---|
| design 文档未登记 | `art === undefined` | 消息含「未登记」+ `reqboard_submit(kind=design)` | 台账 comment（既有） |
| design 文档已登记未落章 | `art.confirmedAt === undefined` | 消息含「待确认」+ `reqboard_ask_confirm` | 台账 comment |
| 已确认但仍有未登记新增件 | ask_confirm 早返回前跑 G2 | 补 `gate_failure` + 「仍有 N 份未登记」 | 返回体 + comment |
| 弹框超宽限未作答 | 宽限计时器到期 | 返回 `pending+ticket`，**不判失败**；后台续跑 | 完成时写 comment |
| 零参调用 | 绑定层 `decodeWorkerJson(undefined)` | 缺省 `{}`，正常派发 | 无 |
| 位置缺省 | `doc_location` 未传 | 回落 `docs/requirements/<REQ>/` 并记 `defaults_used` | 返回体 + 台账 `docBasePath` |
| 内容闸门消息缺 why/how | 契约测试 TC-21 逐 code 断言 | 视为契约破坏，补齐 `envelope()` 拼接 | 测试红即暴露 |

## 部署与回滚 <!-- serves: FR-3, FR-4, FR-5, FR-8 -->

| 变更 | 生效方式 | 回滚影响 |
|---|---|---|
| 插件源码（FR-1/2/3/5/6/7/8） | worktree 开发 → 合并 → `python3 scripts/relink-profile.py` → 重启 :13080 | 无数据迁移；新增字段可选，旧码忽略 |
| pnpm patch（FR-4） | `pnpm install` 应用 patch 并更新 lockfile | 删除 patch 条目 + 重装即回滚；无数据影响 |
| 提示词分片（FR-5） | 重跑内联脚本 + 重启 | 恢复旧 .md + 重跑即回滚 |

> **部署铁律**：pmboard 是 :13080 实际加载的插件，必须走 worktree + `relink-profile.py --check` 体检，
> 避免硬链接副本静默停在旧版本（CLAUDE.md 记载的事故）。

## 开放问题 <!-- serves: FR-3, FR-6 -->

| 编号 | 问题 | 影响 | 需要谁决策 |
|---|---|---|---|
| OQ-1 | A3 字面要求「同一次调用内在 5 分钟后返回 confirmed=true」。非阻塞投递下，该字面只能由「回执/唤醒后拿到 confirmed=true」满足；若必须同调用返回，只能抬高调用方预算（`dsh-ptc-runtime-node` 默认 120s，上限 600s），属宿主配置改动 | FR-3 验收口径 | 人（确认闸门） |
| OQ-2 | 若要宿主**自动**探测 upstream TIMEOUT 并写入断点，需要 DSH 回合事件接入（超本次边界）；本设计以「交棒即写 checkpoint（总是最新）」+ `reqboard_note_interruption` 显式补写满足 | FR-6 自动化程度 | 人（确认闸门） |

修订记录：v1 · 2026-09-24 · 本窗口 · 初稿