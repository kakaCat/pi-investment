---
requirement_refs: [FR-1, FR-2, FR-3, FR-6, FR-7]
---

# 数据模型（REQ-260924213231-b1c4）

> 读者：工程 / agent。持久化载体是单一 JSON 台账（`.dsh-data/dsh-reqboard.json`，
> 经 `adapters/JsonLedgerRepository` 原子写）。**本次不新增持久化集合**，只加两个可选字段 + 两个派生投影。

## 实体关系 <!-- serves: FR-1, FR-3, FR-6 -->

```
┌────────────────────┐ 1        n ┌──────────────────┐
│ RequirementRecord  │ ────────── │ StageArtifact     │
│  + interruption?   │            │  kind=design      │
│  + docBasePath?    │            │  confirmedAt?     │
└──────────┬─────────┘            └──────────────────┘
           │ 派生（不持久化）
           ▼
┌────────────────────────┐        ┌──────────────────────────┐
│ DesignDocRegistration  │        │ PendingConfirmation      │
│ (逐份登记态投影)        │        │ (内存 ticket → 状态/回执) │
└────────────────────────┘        └──────────────────────────┘
```

## 表 / 实体 <!-- serves: FR-1, FR-3, FR-6, FR-7 -->

| 编号 | 表/实体 | 用途 | 关键字段 |
|---|---|---|---|
| T-1 | `RequirementRecord.interruption`（新增，可选） | 断点：当前阶段 + 未完成动作 + 中断原因 | `at` / `reason` / `stage` / `pendingAction` / `tool?` |
| T-2 | `RequirementRecord.artifacts[]`（既有，语义收紧） | 设计文档登记与落章 | `kind='design'` / `path` / `confirmedAt` / `registeredBy` / `autoDiscovered` |
| T-3 | `DesignDocRegistration`（派生投影，不落盘） | 逐份登记态，供 `reqboard_status` 与页面 | `name` / `path` / `on_disk` / `registered` / `confirmed` / `exempted?` / `conditional?` |
| T-4 | `PendingConfirmation`（内存，不落盘） | 超宽限的挂起确认 | `ticket` / `windowKey` / `requirementId` / `target` / `kind` / `createdAt` / `outcome?` |
| T-5 | `RequirementRecord.docBasePath`（既有） | 需求文档目录，立项时写入 | string（如 `docs/requirements/<REQ>/`） |

**T-1 字段明细**

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `at` | number | 是 | — | 中断/检查点时间戳（ms） |
| `reason` | string | 是 | "turn interrupted" | 中断原因原文；交棒检查点写 "checkpoint" |
| `stage` | string | 是 | 当前需求状态 | 断点时的流水线阶段 |
| `pendingAction` | string | 是 | — | 未完成动作（下一步工具命令），如 `reqboard_ask_confirm(target=artifact, kind=design)` |
| `tool` | string | 否 | — | 最后成功调用的工具名 |

**T-1 的 `reason` 取值（`turn/end` 事件驱动，值域取自宿主 `TurnEndReasonMap`）**

| `turn/end.data.reason.kind` | 是否异常 | 写进 `interruption.reason` | 说明 |
|---|---|---|---|
| `completed` | 否 | （不补写，保留 A 的 `checkpoint`） | 正常收尾 |
| `max-tokens` | 否 | `max-tokens` | 可续（插件可能已继续回合），不算中断 |
| `blocked` | 否 | `blocked` | 回合被阻塞，非失败 |
| `aborted` | 是 | `aborted:<cause.kind>` | 取消/中断请求 |
| `error` | 是 | `error:<code>:<message>` | **上游流超时落这里**（`error: LlmFailure`） |
| `interrupted` | 是 | `interrupted` | 崩溃孤儿回合（agent-loop resume / 冷读合成） |
| 形态不认识 | — | 不写（`turnEndOutcome` 返回 `undefined`） | 不猜、不误报；A 的 checkpoint 仍在 |

**写入者**：A = 交棒用例的 `stampCheckpoint`（`reason="checkpoint"`，幂等）；
B = `CaptureHook.turn/end` 经异步边界调 `noteInterruption`（覆盖 `reason`）；B′ = `reqboard_note_interruption` 工具。
同一需求只保留**一个** `interruption` 对象（后写覆盖前写），避免「两份真相」。

**T-4 字段明细**

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `ticket` | string | 是 | — | 前缀 `pc-` + 随机 id |
| `windowKey` | string | 是 | — | 归属窗口（防止跨窗口取用） |
| `requirementId` | string | 是 | — | 目标需求 |
| `target` | "artifact" \| "plan" | 是 | — | 与 ask_confirm 同语义 |
| `kind` | ArtifactKind（可选） | 否 | — | target=artifact 时的产物种类 |
| `createdAt` | number | 是 | — | 登记时间（超过 `LIMITS.confirmEvidenceWindowMs` 视为过期） |
| `outcome` | {confirmed:boolean; advanced:boolean; userChoice?:string; userFeedback?:string} | 否 | — | 后台作答后回填 |

## 索引与约束 <!-- serves: FR-1, FR-3, FR-6 -->

| 索引/约束 | 字段 | 理由 |
|---|---|---|
| 产物唯一性（既有） | `artifacts[].stage+kind+path` 不重复 | 登记幂等：`registerArtifact` 与发现核心共用同一判据 |
| 落章成组（既有） | 全部 `kind=design` 一次落章 | `artifactsToConfirm`，保证「一次确认 = 全部设计文档有章」 |
| 断点单值 | `RequirementRecord.interruption` 单对象 | 同一时刻只有一个断点，避免「两份真相」 |
| ticket 唯一 | `PendingConfirmation.ticket` 全局唯一 | 回执按 ticket 精确定位 |
| ticket 窗口绑定 | `windowKey` 必须等于调用窗口 | 回执不可跨窗口取用 |

## 版本兼容 <!-- serves: FR-1, FR-3, FR-6, FR-7 -->

| 问 | 答 |
|---|---|
| 旧数据怎么办？ | `interruption` 缺失 = 无断点，输入包不渲染该节；`artifacts` 为 undefined/空 的 legacy 需求继续走 `isLegacy` 放行 |
| 旧调用方怎么办？ | 返回体只增键；`reqboard_create` 不传 `doc_location` 时 `docBasePath` 写既有缺省值，`requirementDocPath()` 输出逐字节不变 |
| 可否回滚？ | 可：移除字段读取代码即可；新增字段留在台账里不产生副作用（消费者忽略） |
| 需要数据回填吗？ | **不需要**。`interruption` 由后续交棒/中断自然写入；`design` 产物由 `reqboard_submit(kind=design)` 或看板自动发现补齐 |

## 迁移与灰度 <!-- serves: FR-1, FR-4, FR-5 -->

| 项 | 方案 |
|---|---|
| 开关 | **不引入新开关**（避免两份行为）；FR-3 的宽限窗口走既有配置面 `LIMITS`，可调不可关 |
| 灰度 | 无需服务端灰度：单进程插件，重启即全量；先合并 FR-1/FR-2（无行为风险）再上 FR-3（行为变化最大） |
| 回填 | 历史需求（如 REQ-260924162957-2cd3）修复后可直接 `reqboard_submit(kind=design)` 补齐登记并走通 |
| 回滚路径 | 插件回退到上一版本构建；FR-4 删除 patch 条目后重装；均无数据迁移 |