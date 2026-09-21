---
req_id: REQ-4842fe
doc: design/data-model
serves: FR-1, FR-1b, FR-2, FR-5, FR-6, FR-14, FR-15
status: design
---

# REQ-4842fe 设计 · 数据契约与迁移

## 1. TaskRecord 扩展字段  `serves: FR-2`

全部为**可缺省加字段**（旧台账读出即旧行为，不 bump schemaVersion）：

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `parentId` | string? | 否 | 有值 = 子卡，指向父卡 id；无值 = 普通/父卡（存量卡行为不变） |
| `stageKind` | StageKind? | 子卡必填 | `dev` / `integrate` / `review` / `test` / `repro` / `fix` / `regress` / `probe` / `collect` / `analyze` / `prepare` / `run` / `verify` / `change` / `dryrun` / `apply` |
| `attempt` | number | 否（默认 0） | 失败重跑次数，失败回退时 +1 |
| `revisions` | CardRevision[] | 否（默认 []） | 卡片修订记录（见 §6） |

**派生关系**：父卡不存子卡 id 列表——子卡由 `parentId` 反查得出（单一事实源，避免双写不一致）。

```ts
interface CardRevision {
  at: number                    // 时点
  by: ActorRef                  // 操作者（agent / system / human）
  kind: "update" | "rollback" | "reopen"
  reason: string                // 触发原因：哪次失败 / 哪条需求描述变更 / 人工重开
  changes: string[]             // 字段级变更摘要，如 ["acceptance: 改为..." , "dependsOn: +t-xxx"]
}
```

**父卡依赖继承**：子卡链首卡的 `dependsOn` = 父卡的 `dependsOn`（跨父卡顺序仍由父卡层表达）；链内第 n 卡依赖第 n-1 卡。

## 2. 子卡集合映射表与逃生舱口  `serves: FR-1, FR-1b`

**单点位置**：`domain/task/SubtaskTemplate.ts`（纯数据 + 纯函数，零 I/O）。

| 父卡类型 | 默认子卡集合（有序） |
|---|---|
| feature / refactor | dev → integrate → review → test |
| bug | repro → fix → review → regress |
| doc | dev → review |
| chore | dev → review |
| spike | probe → review |
| research / analysis | collect → analyze → review |
| data | prepare → run → verify → review |
| ops | change → dryrun → apply → verify → review |
| review-only | review |
| 未映射 / 未知 | dev → review（保守回退） |

**逃逸契约（FR-1b）**：拆分计划里可为**单张卡**声明 `stages: StageKind[]`（覆盖映射表）。校验三条：
1. 元素必须取自受控 `StageKind` 枚举（拒绝自由文本）；
2. 非空、无重复；
3. 每张子卡的 acceptance 仍须可证伪（沿用现有薄卡门禁口径）。

**每张子卡的默认 acceptance 模板**（映射表附带，必须可证伪）：例：`dev` = 改动落盘且相关测试/命令可跑通并给出输出；`review` = 对设计与实现的偏离逐条给出结论；`test` = 目标命令输出全绿。

## 3. 子卡状态机（收紧四态）  `serves: FR-5`

```
子卡：todo → in_progress → done        （canceled 仅人工；不进 integrating/testing/in_review）
父卡：todo → in_progress → done        （中段由子卡链承载）
存量卡：todo→in_progress→integrating→testing→in_review→done（原样，不改）
```

**实现方式**：`assertTaskTransition(from, to, actor, role)` 增加 role 入参（`parent` | `subtask` | `legacy`）；子卡使用独立转移表 `SUBTASK_TRANSITIONS`：

```ts
SUBTASK_TRANSITIONS = {
  todo:        ["in_progress", "canceled"],
  in_progress: ["done", "todo", "canceled"],   // todo = 失败回退
  done:        ["in_progress", "canceled"],    // 仅人工门：返工重开（见 §6）
  canceled:    ["todo"],
}
```

人工门新增：`done>in_progress`（重开）、`done>canceled` 及各级 `>*>canceled`（取消，沿用既有口径）。

## 4. 完工凭证口径  `serves: FR-6`

现有 `assertDoneEvidence` 含"本窗口工具活动"检查，而干活子代理在**别的会话**，该检查对子卡恒不成立。分口径处理：

**子卡（三项全过）**：
1. 子卡 report 非空（由调度器从 run 产出生成，含 filesChanged / 命令 / 证据摘要）；
2. filesChanged 至少一个文件真实存在且 `mtime ≥ 子卡 in_progress 时刻`（与窗口无关的文件系统证据）；
3. run 的 `stopReason === completed` 且返回值经 realm 物化非空。

**父卡（沿用汇总口径）**：父卡 report（由子卡 report 合成）+ 全部子卡 done + 通过既有 done 凭证门的其余校验。

**豁免范围**：子卡跳过"本窗口工具活动"与"60 秒完工节流"（这两条是为人工窗口防刷设计的）；**页面插件构建新鲜度校验保留**（对 pages 源码的改动仍要求 client 产物更新）。

## 5. 需求状态机新增转移  `serves: FR-14`

**现状缺口**：`RequirementStatus.ts:61` `implementing: [accepting, canceled]` —— 没有回退上游路径。

**新增**：`implementing → design`，列入 `HUMAN_ONLY_REQ_TRANSITIONS`（人工门；`MoveRequirement.ts:57` 的 gateConfirmed 通道同样适用）。

**新增需求级字段**：`autoRun?: boolean`（默认 false；与既有字段同层，可缺省）。semantics：
- `true` = 自动链运行中；`false` = 暂停（失败 / 熔断 / 人工关闭）；
- 落库时机：批准计划时置 true；PAUSE 事件置 false；人点"继续"置 true 并触发一次事件；
- 持久化在台账内（非内存），重启后由恢复扫描读取。

## 6. 卡片修订记录与重开  `serves: FR-15`

**触发点与写法**：

| 情形 | kind | 写法 |
|---|---|---|
| 返工回上游后重新批准计划，受影响父卡被就地更新 | `update` | reason = 关联的需求描述变更原因；changes = 字段级摘要 |
| 子卡失败回退（in_progress → todo） | `rollback` | reason = 失败原因摘要；changes = `["attempt: n→n+1"]` |
| done 卡被人工重开 | `reopen` | reason = 人工填写；changes = `["status: done→in_progress"]` |

**纪律**：修订只增不改（append-only）；修订与状态变更写在同一 `mutate` 事务内（原子）；**不新增重复卡、不把受影响卡置 canceled**（用户裁定：更新旧卡）。

**done 卡重开的前提**：仅当该卡被新需求描述推翻时由**人工**触发；自动链不得重开 done 卡。重开后 rollup 重新计算；若需求已进 accepting，沿用既有 `accepting → implementing` 退回。

## 7. 迁移与兼容  `serves: FR-2, FR-5`

- **纯加字段**：无 schemaVersion bump；旧台账（无 parentId / revisions / autoRun）读出即旧行为；
- **双模共存**：无 `parentId` 的卡走既有五段状态机与人工推进；`role` 判定为 `legacy`；
- **不做存量迁移**：不批量补子卡、不改既存卡；
- **回滚路径**：`autoRun=false` 或撤下 `reqboard_task_run` 工具即回手动模式；已生成子卡不出问题（可用 task_move 手动推进）；
- **新工具对旧卡的行为**：`reqboard_task_run` 作用于无子卡的普通卡时，先懒展开再执行（等价于新式父卡）。

## 8. 不变量（INV）  `serves: FR-2, FR-5, FR-6`

| INV | 内容 | 违反后果 |
|---|---|---|
| INV-1 | 子卡的 `parentId` 必须指向同需求内存在的父卡 | 悬空子卡 |
| INV-2 | 子卡必须有 `stageKind`，且父卡不得有 `stageKind` | 角色混乱 |
| INV-3 | 子卡集合 = 映射表或显式 stages 的确定性投影（同一父卡重复展开幂等，不产生第二套） | 重复落卡 |
| INV-4 | 子卡链依赖成环 = 非法（沿用既有 DAG 成环校验） | 死锁 |
| INV-5 | 父卡 done 时其全部子卡必须 done | 带病收尾 |
| INV-6 | `revisions` 只增不改，时间戳单调 | 审计失真 |
| INV-7 | 同需求同时 in_progress 父卡数 ≤ 上限 | 冲突面失控 |
