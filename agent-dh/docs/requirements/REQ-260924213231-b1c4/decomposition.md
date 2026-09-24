---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8]
---

# 拆分计划（REQ-260924213231-b1c4）

> 目标一句话：让 agent 在设计→拆分这一步**只靠工具**就能走通——设计文档有可调用的登记入口、
> 被闸门拦下时看得懂「未登记 / 待确认」两种病因与唯一下一步、人在环弹框不被调用方执行预算掐断。
>
> 做法一句话：把「扫目录→登记产物」从只挂 HTTP 渲染的 `ArtifactSync` 下沉为 **application 纯函数 +
> `reqboard_submit(kind=design)` 工具**（FR-1）；G2 闸门按病因**分叉文案**并统一「what+why+how」拒绝信封（FR-2）；
> 弹框改**投递+回执**非阻塞（FR-3）；零参绑定打最小 patch（FR-4）；设计提示词写明登记命令（FR-5）；
> 断点**常驻台账**并由输入包带出（FR-6）；立项降级路径补 `doc_location`（FR-7）；pm 弹框统一来源标志（FR-8）。
>
> 本计划须**人批准**后才能落任务卡（reqboard_decompose）。**覆盖不齐不许批**。

## 编号口径

| 编号 | 出自 | 指什么 |
|---|---|---|
| FR-x | requirement.md 功能点表 | 需求条款（本需求 FR-1 ~ FR-8） |
| I-x | design/interfaces.md 接口清单 | 接口契约（I-1 ~ I-9） |
| T-x | design/data-model.md 表/实体 | 数据实体（T-1 ~ T-5） |
| UC-x | design/use-cases.md 场景总览 | 用户场景（UC-1 ~ UC-6） |
| TC-x | design/test-cases.md 用例表 | 测试用例（TC-1 ~ TC-22） |
| t-x | 本文档任务表 | 任务（**本计划用大写 `T-n` 作计划 key**，见「设计偏差 D-0」） |

## 改动盘点（新增 / 修改 / 删除）

### 新增（13 个源文件 + 11 个测试文件 + 1 个 patch）

| 文件 | 内容 | 对应 |
|---|---|---|
| `packages/web/dsh-pmboard/src/application/internal/artifact-discovery.ts` | `discoverArtifactsFrom(docs, req)` 纯函数：目录→待登记产物（唯一发现实现） | I-1、FR-1 |
| `packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts` | `submitDesignArtifacts(deps,args,exec)`：一次 mutate 幂等登记 + 逐份态 | I-1、FR-1 |
| `packages/web/dsh-pmboard/src/tools/ConfirmReceiptTool/ConfirmReceiptTool.ts` | `reqboard_confirm_receipt(ticket)` 工具壳 | I-4、FR-3 |
| `packages/web/dsh-pmboard/src/adapters/PendingConfirmRegistry.ts` | 内存 `ticket→状态` 注册表（窗口绑定 + 过期） | T-4、FR-3 |
| `packages/web/dsh-pmboard/src/application/use-cases/ConfirmReceipt.ts` | 回执查询用例（以台账为准，幂等） | I-4、FR-3 |
| `packages/web/dsh-pmboard/src/application/internal/gate-feedback.ts` | `envelope(f)`：拒绝消息三要素统一拼接（唯一入口） | I-9、FR-2 |
| `packages/web/dsh-pmboard/src/application/internal/interruption.ts` | `turnEndOutcome` / `nextActionFor` / `stampCheckpoint` / `stampInterruption` | T-1、FR-6 |
| `packages/web/dsh-pmboard/src/application/use-cases/NoteInterruption.ts` | 补写断点用例（B′ 入口） | I-8、FR-6 |
| `packages/web/dsh-pmboard/src/tools/NoteInterruptionTool/NoteInterruptionTool.ts` | `reqboard_note_interruption(reason)` 工具壳 | I-8、FR-6 |
| `packages/web/dsh-pmboard/src/domain/text/pm-badge.ts` | `pmHeader(text)` → `📋 PM · {text}`（来源标志唯一注入点） | I-7、FR-8 |
| `packages/web/dsh-pmboard/src/plugin-config.ts` | 从 index.ts 抽出的配置/路径/开关纯函数（含 `dshHomePath`/`nodeIsolationEnabled` 再导出） | D-2、尺寸门禁 |
| `packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts` | 从 index.ts 抽出的捕获 hook 组合装配 | D-2、尺寸门禁 |
| `patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch` | 绑定工厂缺省参数 `(args = {})`（FR-4 唯一改动） | I-5、FR-4 |
| `packages/web/dsh-pmboard/tests/contract-shapes.test.ts` 等 11 个测试文件 | 见「测试文件落点」 | TC-1~TC-22 |

### 修改（关键文件）

| 文件 | 改动 | 对应 |
|---|---|---|
| `packages/web/dsh-pmboard/src/shared/protocol.ts` | 增 `InterruptionRecord` / `DesignDocRegistration` / `PendingConfirmation`；`RequirementRecord.interruption?` | T-1/T-3/T-4 |
| `packages/web/dsh-pmboard/src/application/ports.ts` | 增 `PendingConfirmPort` 端口 + `UseCaseDeps.pendingConfirms?` | I-4 |
| `packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts` | 改为薄壳：调 `discoverArtifactsFrom` + 落库（行为零变更） | FR-1 |
| `packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts` | `SUBMIT_KINDS` 增 `design` + 分派表 + 输出 schema | I-1、FR-1 |
| `packages/web/dsh-pmboard/src/application/internal/design-docs.ts` | 增 `designDocRegistration`：合并磁盘/产物簿/确认章三源 | T-3、FR-1 |
| `packages/web/dsh-pmboard/src/application/query/QueryState.ts` + `src/tools/StatusTool/StatusTool.ts` | `reqboard_status` 返回 `design_docs[]` 与 `interruption?` | I-2、FR-1/FR-6 |
| `packages/web/dsh-pmboard/src/application/internal/design-gates.ts` | G2 gap 按 `art===undefined`（未登记）/`confirmedAt===undefined`（待确认）分叉 | I-9、FR-2 |
| `packages/web/dsh-pmboard/src/application/internal/content-gate-wiring.ts` | 全部 `GateFailure.message` 改走 `envelope()`（判定逻辑不动） | I-9、FR-2 |
| `packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts` | 已确认早返回补 G2 缺口；宽限+挂起+后台落章；header 走 `pmHeader`；mutate 尾 `stampCheckpoint` | I-3、FR-2/3/6/8 |
| `packages/web/dsh-pmboard/src/domain/limits.ts` | 增 `confirmInlineGraceMs`（宽限窗口，可调不可关） | FR-3 |
| `packages/web/dsh-pmboard/src/adapters/CaptureHook.ts` | 增 `onTurnFinished?` 信号（turn/end 只发信号，D-17） | FR-6 |
| `packages/web/dsh-pmboard/src/application/internal/node-input-package.ts` | 条件追加「## 断点」节（无字段则逐字节不变） | FR-6 |
| `packages/web/dsh-pmboard/src/application/use-cases/SubmitArtifact.ts` / `MoveRequirement.ts` / `Decompose.ts` / `MoveTask.ts` / `AcceptSheet.ts` | 各 mutate 尾调 `stampCheckpoint` | FR-6 |
| `packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts` + `src/application/use-cases/CreateRequirement.ts` + `src/application/internal/support.ts` | 增 `doc_location` 入参 → `docBasePath` + `defaults_used` + 推进终态 | I-6、FR-7 |
| `packages/web/dsh-pmboard/src/domain/prompt/fragments/design/{light,heavy}/overrides.md` + `generated/fragments.ts` | 覆盖条目 1 改写：登记命令 + 触发者 + 「不要猜 kind」 | FR-5 |
| `packages/web/dsh-pmboard/src/application/internal/capture-mapping.ts` + `src/application/use-cases/HandleFailure.ts` | 弹框 header 走 `pmHeader` | I-7、FR-8 |
| `packages/web/dsh-pmboard/src/index.ts` | 装配 `PendingConfirmRegistry`/`interruption` 接线；注册 2 个新工具；**瘦身至 ≤400 行** | FR-3/6、尺寸门禁 |
| `packages/web/dsh-pmboard/tests/design-completeness-gate.test.ts` | 按 FR-2 文案分化校准断言（未登记/待确认） | FR-2 |

### 删除

| 项 | 结论 |
|---|---|
| 无 | 本次纯新增/修改，不删文件、不迁移数据、不改台账必填字段 |

## 设计偏差与实现决策（须人可见）

- **D-0 计划 key 用大写 `T-1`~`T-13`**：`taskRefsFromDecomposition` 的任务编号识别式为
  `(?:T|BE|FE|TC|E)-\d+|t-[0-9a-f]{6}`，小写 `t1` **不被识别** → 计划批准后自动拆分时覆盖门禁读不到
  RTM 绑定（会撞 `requirement_uncovered`）。故用大写 `T-n`（仍满足 `reqboard_decompose` 的 key 集合一致性校验）。
  同因，RTM 表头用「任务 id / 需求条款 / 任务标题」，任务表列名用「覆盖条款」（避免两表重复解析）。
- **D-1 前置基线是红的（须人知悉，见「基线缺口」）**：`packages/web/dsh-pmboard` 在 `main` 上
  `npx vitest run` 已有 **7 文件 / 9 用例失败**、`tsc --noEmit` 有 **23 条类型错误**——其中
  `tests/design-completeness-gate.test.ts`（2 例）**正好落在本需求 FR-2 的 ask_confirm 缺口返回路径上**，
  由 T-5 一并修复；其余（template 地址段 2 例、layer-boundary 1 例、typecheck 23 条、size-budget 1 例、
  client-view 1 例、repository 1 例）**不属本需求范围**，本次只保证「不新增失败」并把 size-budget 修绿（T-12）。
- **D-2 `index.ts` 已 434 行 > 400（尺寸门禁红）**：本需求的 FR-3/FR-6 接线**也要落在 `index.ts`**，
  若不处理会让门禁继续恶化。故单列 T-12 把配置/路径纯函数与捕获根装配抽到
  `src/plugin-config.ts` / `src/wiring/pm-capture-root.ts`（`dshHomePath`/`nodeIsolationEnabled` 由 index.ts
  **再导出**以保持既有 import 兼容），把 `index.ts` 降到 ≤400 行使 `tests/size-budget.test.ts` 转绿。
- **D-3 FR-2 只改文案不改判定**：`GateFailure.code` 与 `gaps` 结构**一律不动**（NFR-2 护栏强度不降），
  仅把 `message` 拼接统一到 `gate-feedback.ts` 的 `envelope()`。T-5 用逐 code 断言锁死「what+why+how」。
- **D-4 FR-6 不做宿主回合事件探测**：上游 TIMEOUT 发生后 pmboard 已无执行机会，故断点靠
  **交棒即写 checkpoint（总是最新）** + `turn/end` 事件补原因 + `reqboard_note_interruption` 显式兜底两层，
  `turnEndOutcome` 对不认识的事件形态返回 `undefined`（不猜、不误报）。事件入口挂 `CaptureHook` 已订阅的
  `turn/end`，经组合根异步边界（`setImmediate`）写台账，监听器内不做会话写操作（D-17）。
- **D-5 弹框非阻塞不改宿主 schema**：FR-3 用「投递 + 回执」实现，宽限内作答保持与旧语义**逐字一致**；
  超宽限返回 `pending+ticket`（**不判失败**），后台落章+推进+经 `AgentDeliverer` 唤醒窗口；
  回执缺 ticket 时回退读台账 `confirmedAt`（幂等，以台账为准）。不抬高调用方 120s 预算（OQ-1 的宿主改动不做）。
- **D-6 `AskConfirm.ts` 已 359 行（贴近 400 上限）**：T-5/T-6/T-9/T-11 都要动它，实现时把
  「后台落章+推进」抽到 `ConfirmReceipt.ts` 侧、checkpoint 逻辑留在 `interruption.ts`，
  保证每步后该文件仍 ≤400 行（否则 `tests/size-budget.test.ts` 红）。

## 任务表

| 计划 key | 任务 id | 标题 | 覆盖条款 | 落点（编号+文件） | 阶段 | 端侧 | 依赖 | 工作量 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| T-1 | （落库后回填） | 定义新契约类型与端口 | FR-1, FR-3, FR-6, FR-7 | T-1/T-3/T-4 + `packages/web/dsh-pmboard/src/shared/protocol.ts`、`packages/web/dsh-pmboard/src/application/ports.ts`、`packages/web/dsh-pmboard/tests/contract-shapes.test.ts` | implement | backend | — | M | `npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts` 全绿；`npx tsc --noEmit -p tsconfig.json` 错误数 ≤ 基线 23 且新增文件 0 报错 |
| T-2 | （落库后回填） | 下沉产物发现核心并薄壳化 ArtifactSync | FR-1 | I-1 + `packages/web/dsh-pmboard/src/application/internal/artifact-discovery.ts`、`packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts`、`packages/web/dsh-pmboard/tests/sync-artifacts.test.ts` | implement | backend | T-1 | M | `npx vitest run tests/sync-artifacts.test.ts` 全绿且既有断言逐字不变；`npx vitest run tests/layer-boundary.test.ts` 不新增越界（新增文件位于 application 且不 import node:/adapters） |
| T-3 | （落库后回填） | 新增 kind=design 登记用例与工具入口 | FR-1 | I-1 + `packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts`、`packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts`、`packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts`、`packages/web/dsh-pmboard/tests/design-registration.test.ts` | implement | backend | T-2 | M | `npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts` 全绿；TC-1 首次 `registered_count=5`、二次 `=0`；空目录返回 0 且不谎报成功 |
| T-4 | （落库后回填） | 投影逐份登记态到 reqboard_status | FR-1 | T-3 + `packages/web/dsh-pmboard/src/application/internal/design-docs.ts`、`packages/web/dsh-pmboard/src/application/query/QueryState.ts`、`packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts`、`packages/web/dsh-pmboard/tests/tools-status.test.ts` | implement | backend | T-3 | M | `npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts` 全绿；`design_docs[]` 的 on_disk/registered/confirmed 三态与磁盘+台账逐份一致 |
| T-5 | （落库后回填） | 分化 G2 闸门文案并统一拒绝信封 | FR-2 | I-9 + `packages/web/dsh-pmboard/src/application/internal/gate-feedback.ts`、`packages/web/dsh-pmboard/src/application/internal/design-gates.ts`、`packages/web/dsh-pmboard/src/application/internal/content-gate-wiring.ts`、`packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts`、`packages/web/dsh-pmboard/tests/design-gate-messages.test.ts`、`packages/web/dsh-pmboard/tests/gate-feedback-envelope.test.ts`、`packages/web/dsh-pmboard/tests/design-completeness-gate.test.ts` | implement | backend | T-4 | L | `npx vitest run tests/design-gate-messages.test.ts tests/gate-feedback-envelope.test.ts tests/design-completeness-gate.test.ts` 全绿（含基线 2 个历史红例）；未登记消息含「未登记」+ `reqboard_submit(kind=design)`，待确认消息含「待确认」+ `reqboard_ask_confirm`，两串不相同；逐 code 断言含 `——` 与 `补齐：` |
| T-6 | （落库后回填） | 弹框改非阻塞投递并加回执工具 | FR-3 | I-3/I-4 + `packages/web/dsh-pmboard/src/domain/limits.ts`、`packages/web/dsh-pmboard/src/adapters/PendingConfirmRegistry.ts`、`packages/web/dsh-pmboard/src/application/use-cases/ConfirmReceipt.ts`、`packages/web/dsh-pmboard/src/tools/ConfirmReceiptTool/ConfirmReceiptTool.ts`、`packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts`、`packages/web/dsh-pmboard/src/index.ts`、`packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts` | implement | backend | T-5 | L | `npx vitest run tests/ask-confirm-pending.test.ts tests/ask-confirm.test.ts tests/size-budget.test.ts` 中 ask-confirm 两文件全绿；`questions.ask` 永不 resolve + 宽限 20ms → 返回 `pending=true` 且 ticket 非空、不抛错；作答后 `reqboard_confirm_receipt(ticket)` 返回 `confirmed=true, advanced=true` 且台账 confirmedAt 已写 |
| T-7 | （落库后回填） | 打零参绑定 patch | FR-4 | I-5 + `patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch`、`package.json`、`packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts` | implement | backend | — | S | `npx vitest run tests/zero-arg-binding.test.ts` 全绿且断言 patch 后 `lib/process.js` 绑定工厂为 `(args = {})`；在本窗口 run_code 内只调 `tools.reqboard_status()`（零参）→ 正常返回，输出无 `binding arguments must be lossless JSON` |
| T-8 | （落库后回填） | 设计提示词写明登记命令 | FR-5 | I-1 + `packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md`、`packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md`、`packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts`、`packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts` | doc | doc | T-3 | S | `node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs` 退出 0；`npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts` 全绿；design/light 与 heavy 文本含 `reqboard_submit(kind=design)`，且不含「落盘即产物」旧断言 |
| T-9 | （落库后回填） | 实现断点常驻与续跑输入包 | FR-6 | T-1 + `packages/web/dsh-pmboard/src/application/internal/interruption.ts`、`packages/web/dsh-pmboard/src/application/use-cases/NoteInterruption.ts`、`packages/web/dsh-pmboard/src/tools/NoteInterruptionTool/NoteInterruptionTool.ts`、`packages/web/dsh-pmboard/src/adapters/CaptureHook.ts`、`packages/web/dsh-pmboard/src/application/internal/node-input-package.ts`、`packages/web/dsh-pmboard/src/application/use-cases/SubmitArtifact.ts`、`packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`、`packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`、`packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts`、`packages/web/dsh-pmboard/src/application/use-cases/AcceptSheet.ts`、`packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts`、`packages/web/dsh-pmboard/src/index.ts`、`packages/web/dsh-pmboard/tests/interruption-checkpoint.test.ts` | implement | backend | T-6 | L | `npx vitest run tests/interruption-checkpoint.test.ts` 全绿：只交棒 → 台账 `interruption.reason==='checkpoint'` 且 pendingAction 非空；喂 `turn/end` 且 `reason.kind='error'` → reason 变 `error:UPSTREAM_STREAM_IDLE:…`；重建输入包含 `## 断点` 与 pendingAction；老需求无字段 → 输入包逐字节不变 |
| T-10 | （落库后回填） | 立项降级路径不丢文档位置 | FR-7 | I-6 + `packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts`、`packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts`、`packages/web/dsh-pmboard/src/application/internal/support.ts`、`packages/web/dsh-pmboard/tests/create-doc-location.test.ts` | implement | backend | T-1 | M | `npx vitest run tests/create-doc-location.test.ts` 全绿；不传 doc_location → 返回 `doc_location='docs/requirements/<REQ>/'` 且 `defaults_used` 含 doc_location、台账 docBasePath 同值；传 `docs/rfcs/` → 台账 docBasePath 与产物路径按它生成；返回 status 与台账一致 |
| T-11 | （落库后回填） | pm 弹框统一来源标志 | FR-8 | I-7 + `packages/web/dsh-pmboard/src/domain/text/pm-badge.ts`、`packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts`、`packages/web/dsh-pmboard/src/application/use-cases/AcceptSheet.ts`、`packages/web/dsh-pmboard/src/application/internal/capture-mapping.ts`、`packages/web/dsh-pmboard/src/application/use-cases/HandleFailure.ts`、`packages/web/dsh-pmboard/tests/pm-question-badge.test.ts` | implement | backend | T-9 | M | `npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts` 全绿；ask_confirm / accept_sheet / capture 四问 / 失败处置四处 `AskQuestion.header` 均以 `📋 PM · ` 开头；宿主原生 ask_user_question 不带该前缀 |
| T-12 | （落库后回填） | 组合根瘦身使尺寸门禁转绿 | —（工程规范，不接 FR） | D-2 + `packages/web/dsh-pmboard/src/index.ts`、`packages/web/dsh-pmboard/src/plugin-config.ts`、`packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts` | implement | backend | T-9 | M | `npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts` 全绿；`wc -l packages/web/dsh-pmboard/src/index.ts` ≤ 400；`nodeIsolationEnabled` 仍可从 `src/index.ts` import 且行为不变 |
| T-13 | （落库后回填） | 迁移兼容卡与 E2E 复跑 | FR-1, FR-6 | T-1/T-3 + `packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts`、`packages/web/dsh-pmboard/tests/migration.test.ts` | test | fullstack | T-1, T-2, T-3, T-4, T-5, T-6, T-7, T-8, T-9, T-10, T-11, T-12 | M | `npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts` 全绿；E2E 落盘 5 份 design → submit(design) → ask_confirm → move(decomposing) 一次通过且全程无 `REQBOARD_MISSING_ARTIFACT`；legacy（artifacts 空）需求仍放行；`npx vitest run` 失败集合 ⊆ 基线且不新增失败 |

## RTM 绑定（任务 ↔ 需求条款）

> 覆盖门禁的事实源：每行**一条**条款（`collectIds` 只取首个编号，故一值一行）。
> 任务 id 用计划 key `T-n`（D-0）；「任务标题」列供 `clauseReceiveStatus` 把计划 key 解析回真实任务 id。

| 任务 id | 需求条款 | 任务标题 |
|---|---|---|
| T-1 | FR-1 | 定义新契约类型与端口 |
| T-1 | FR-3 | 定义新契约类型与端口 |
| T-1 | FR-6 | 定义新契约类型与端口 |
| T-1 | FR-7 | 定义新契约类型与端口 |
| T-2 | FR-1 | 下沉产物发现核心并薄壳化 ArtifactSync |
| T-3 | FR-1 | 新增 kind=design 登记用例与工具入口 |
| T-4 | FR-1 | 投影逐份登记态到 reqboard_status |
| T-5 | FR-2 | 分化 G2 闸门文案并统一拒绝信封 |
| T-6 | FR-3 | 弹框改非阻塞投递并加回执工具 |
| T-7 | FR-4 | 打零参绑定 patch |
| T-8 | FR-5 | 设计提示词写明登记命令 |
| T-9 | FR-6 | 实现断点常驻与续跑输入包 |
| T-10 | FR-7 | 立项降级路径不丢文档位置 |
| T-11 | FR-8 | pm 弹框统一来源标志 |
| T-13 | FR-1 | 迁移兼容卡与 E2E 复跑 |
| T-13 | FR-6 | 迁移兼容卡与 E2E 复跑 |

## 覆盖对照

| 需求条款 | 接口（interfaces） | 模块/实体（backend/data-model） | 测试用例（test-cases） | 接收任务 | 完整性 |
|---|---|---|---|---|---|
| FR-1 登记入口 agent 可调 | I-1, I-2 | T-2/T-3 + artifact-discovery / SubmitDesignArtifacts | TC-1, TC-19（2） | T-1, T-2, T-3, T-4, T-13（5） | ✅ |
| FR-2 两种病因文案区分 | I-3, I-9 | gate-feedback / design-gates | TC-2, TC-3, TC-4, TC-21, TC-22（5） | T-5（1） | ✅ |
| FR-3 弹框不被预算掐断 | I-3, I-4 | T-4 + PendingConfirmRegistry | TC-5, TC-6, TC-7, TC-8, TC-20（5） | T-1, T-6（2） | ✅ |
| FR-4 零参可直接调 | I-5 | ptc 绑定 patch | TC-9（1） | T-7（1） | ✅ |
| FR-5 提示词写清登记路径 | —（提示词文本，无进程内接口） | design/{light,heavy}/overrides | TC-10, TC-17（2） | T-8（1） | ✅ |
| FR-6 断点留痕续跑有据 | I-2, I-8 | T-1 + interruption / node-input-package | TC-15, TC-15b, TC-16（3） | T-1, T-9, T-13（3） | ✅ |
| FR-7 立项降级不丢位置 | I-6 | T-5 + CreateRequirement 回落 | TC-11, TC-12, TC-13（3） | T-1, T-10（2） | ✅ |
| FR-8 pm 弹框可辨识 | I-7 | pm-badge 唯一注入点 | TC-14（1） | T-11（1） | ✅ |
| **合计** | 9 接口 | 8 模块 + 5 实体 | 22 用例 | 13 任务 | 8/8 条款有主 |

## 测试文件落点

| 用例 | 实际文件 | 归属任务 |
|---|---|---|
| TC-1, TC-19(前半) | `packages/web/dsh-pmboard/tests/design-registration.test.ts` | T-3 |
| TC-2, TC-3, TC-4 | `packages/web/dsh-pmboard/tests/design-gate-messages.test.ts` | T-5 |
| TC-21, TC-22 | `packages/web/dsh-pmboard/tests/gate-feedback-envelope.test.ts` | T-5 |
| TC-5, TC-6, TC-7, TC-8, TC-20 | `packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts` | T-6 |
| TC-9 | `packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts` | T-7 |
| TC-10, TC-17 | `packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts` | T-8 |
| TC-15, TC-15b, TC-16 | `packages/web/dsh-pmboard/tests/interruption-checkpoint.test.ts` | T-9 |
| TC-11, TC-12, TC-13 | `packages/web/dsh-pmboard/tests/create-doc-location.test.ts` | T-10 |
| TC-14 | `packages/web/dsh-pmboard/tests/pm-question-badge.test.ts` | T-11 |
| TC-18 | `packages/web/dsh-pmboard/tests/confirm-evidence.test.ts`（既有文件，加断言） | T-5 |
| TC-19(E2E) | `packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts` | T-13 |

## 基线缺口（本仓 `main` 已红，非本需求引入；须人知悉）

> 证据：在 `packages/web/dsh-pmboard` 下 `npx vitest run` →
> `Test Files 7 failed | 140 passed (147)`、`Tests 9 failed | 1761 passed (1770)`；
> `npx tsc --noEmit -p tsconfig.json` → 23 条错误。
> 工作区对已跟踪文件干净（`git status --short` 仅未跟踪文档），故为 `main` 上的既存状态。

| 失败 | 是否本需求范围 | 处置 |
|---|---|---|
| `tests/design-completeness-gate.test.ts`（2 例） | **是**——正是 FR-2 的 ask_confirm 缺口返回路径 | T-5 修复并校准文案断言 |
| `tests/size-budget.test.ts`（index.ts 434 行） | **是**——FR-3/FR-6 也要动 index.ts | T-12 修绿 |
| `tests/typecheck.test.ts`（23 条，主要在 domain/template/*） | 否（REQ-260922213356-4a45 遗留） | 记录；本次验收按「错误数 ≤ 23 且新增文件 0 报错」 |
| `tests/template-address-injection.test.ts`（2 例） | 否 | 记录；不新增失败 |
| `tests/layer-boundary.test.ts`（diag-log.ts import node:fs/node:path） | 否 | 记录；T-2 保证新增 application 文件不越界 |
| `tests/client-view.test.ts`（1 例） | 否 | 记录；不新增失败 |
| `tests/application/repository.test.ts`（RandomIdFactory 格式，1 例） | 否 | 记录；不新增失败 |

## 风险与注意

| 风险 | 缓解（落在哪张卡） |
|---|---|
| RISK-1 计划 key 小写不被编号识别式采集 → 自动拆分撞 `requirement_uncovered` | D-0：全用 `T-n`；T-5/T-13 不依赖此 |
| RISK-2 `AskConfirm.ts` 破 400 行（359 → 加宽限/断点/标志） | D-6：后台落章抽到 ConfirmReceipt；T-6/T-9/T-11 各自验收含 size-budget 断言 |
| RISK-3 并行卡声明同一文件 → `REQBOARD_FILE_CONFLICT` | 依赖已把同文件卡串行：AskConfirm 链 T-5→T-6→T-9→T-11；index.ts 链 T-6→T-9→T-12 |
| RISK-4 断点事件形态不认识 → 误报中断 | D-4：`turnEndOutcome` 返回 `undefined`；T-9 含畸形态断言（`{}` / `{reason:{}}`） |
| RISK-5 非阻塞改造让「快作答」路径回归 | T-6：TC-6/TC-20 断言宽限内作答与已确认早返回与旧语义逐字一致 |
| RISK-6 改了 fragments 忘重跑生成器 | T-8 强制 `check-prompt-fragments.mjs` 退出 0 |
| RISK-7 插件硬链接副本静默停旧版 | 发版走 worktree + `relink-profile.py --check`（CLAUDE.md 铁律），T-13 E2E 前先体检 |

## 覆盖完整性规则

1. 每个 FR-1~FR-8 至少被一张任务卡接收（见「覆盖对照」接收任务列，8/8 有主）。
2. 设计文档里出现、却无人接收的编号 = 超范围设计 → 删掉或回需求补条款；本计划已逐项对照（I-1~I-9 / T-1~T-5 / UC-1~UC-6 / TC-1~TC-22 全部有落点）。
3. 事实源：本表 RTM「任务 id ↔ 需求条款」即 `reqboard_decompose` 覆盖门禁的判定依据（D-0：编号用 `T-n` 形态以通过识别式）。

修订记录：v1 · 2026-09-24 · 本窗口 · 初稿
