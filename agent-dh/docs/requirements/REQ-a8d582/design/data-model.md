# REQ-a8d582 设计·数据契约

> requirement_refs: FR-4
> 上游：[requirement.md](../requirement.md) · 关联：[architecture.md](./architecture.md)

## 1. 新增字段 serves: FR-4

```ts
// src/shared/protocol.ts（与 src/client/types.ts 同步）
interface AcceptanceOverride {
  at: number            // 覆盖时刻（毫秒时间戳）
  by: ActorRef          // 操作人（kind:'human'）
  detail: string        // 覆盖说明原文（前端装配，含计数与条目摘要）
  failed: number        // 通过时验收单里"不通过"的项数
  pending: number       // 通过时验收单里"未裁决"的项数
  noMaterials: boolean  // 通过时是否完全没有验收材料
}

interface RequirementRecord {
  // …既有字段
  acceptanceOverride?: AcceptanceOverride   // 可选：缺省 = 无覆盖
}
```

> **实现期修正（2026-09-20，实施 t-2320d9）**：初稿把字段挂在 `verification` 上，落地时发现
> **无材料通过这一半情形根本没有 verification 对象**（`r.verification === undefined`），挂上去写不进。
> 与其为它凭空造一个"看起来像交过材料"的 verification 记录，不如把覆盖提到**需求级**——
> 一笔覆盖属于"这次验收决定"，需求级落点对两种情形都成立且只有一处。

## 2. 落点理由与替代方案 serves: FR-4

- **选需求级**：覆盖是"这一次验收决定"的属性；`acceptanceOverride.failed/pending/noMaterials` 三个计数把当时的验收面状况一并冻住，看板标记与复盘都能只读这一处。
- **替代方案（不采纳）**：把 `override` 挂 `verification` 上——无材料通过时没有该对象，只能半写；或"无材料时补造一条空 verification"——会让台账看起来像交过材料，属于伪造证据面。
- **必须是可选**：旧台账没有该字段，读取与渲染一律按"无覆盖"处理，不做迁移。

## 3. 迁移 serves: FR-4

无迁移。台账为 JSON 文档存储，新增可选字段对旧记录透明；前端对缺字段按"无覆盖"渲染。

## 4. 回滚 serves: FR-4

1. 客户端恢复按钮既有渲染条件（`req.verification !== undefined`）与确认弹框；
2. 服务端忽略 `confirm_override`、恢复 `missing_artifact` 检查；
3. `override` 字段留着不读不写也不报错（无需数据回滚）。

## 5. 留痕面 serves: FR-4

| 面 | 内容 |
|---|---|
| 台账 | `verification.override`（at / by / detail / failed / pending） |
| 需求评论 | `[验收] 人工验收通过（带覆盖）：{detail}` |
| 状态事件 | `recordStatus` 的 reason 带覆盖说明，进 statusHistory |
