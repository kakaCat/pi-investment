# REQ-9f4a44 实施计划

> 状态：待批准 · 类型：refactor · 绑定窗口：w-24ded829
> 上游需求：[requirement.md](./requirement.md)

## 1. 技术设计（四视角）

### 1.1 后端 / 状态机（host）

**目标形状**：`… → implementing → accepting →（人工验收）→ archived`（无 done）

| 改动 | 说明 |
|---|---|
| `REQ_TRANSITIONS` | 新增 `accepting → archived`；移除 `done` 相关转移（`accepting→done`、`done→archived`、`done→canceled` 等） |
| `HUMAN_ONLY_REQ_TRANSITIONS` | 移除 `done>archived`（归档不再是人工门）；`accepting>archived` 仍需人工（验收决定） |
| `ARTIFACT_CONFIRM_GATES` | `accepting>done` → `accepting>archived: 'verification'`；移除 `done>archived` |
| `SYSTEM_REQ_TRANSITIONS` | 保持不变（`implementing>accepting` rollup 仍生效） |
| `ALL_REQ_STATUSES` | **保留 `done` 作为 legacy 可读状态**（老台账不丢），但状态机不允许再进入；`isPlausibleRequirement` 不拒 |
| `assertReqTransition` | 跟随表变更（无硬编码需改，若存在需核对） |

**验收落点**：`handleVerifyDecision(pass=true)` 当前写 `status='done'` → 改为 `'archived'`；
`pass=false`（退回返工）仍回 `implementing`。

**归档材料**：`reqboard_archive_submit` 前置从"done 态"放宽为 `archived` 态可用（archived 下补料）；
备料仍按分类校验（ARCHIVE_DOC_RULES 不变），但不再有人工归档门。

**提示注入**：验收通过后向绑定会话注入"请准备归档材料"（复用 capture-hook 的阶段注入点，
或扩展 stage-prompts 的 archived 段开头加一句"本需求由验收自动归档，请补齐归档材料"）。

### 1.2 前端 / UI（client）

- `conversation-progress.ts` 的 `FLOW`：移除 `done` 格（流程：立项→需求分析→技术设计→拆分→实施→验收→归档）
- `shared/protocol.ts` 的 `CATEGORY_FLOW_PROFILES`：各分类 `stages` 去 `done`，`confirmGates` 同步
- 看板：`archived` 且无 `archive` 产物 → 显示「归档材料待补」标记
- 历史 `done` 记录：看板归入归档泳道或标注「历史完成」，不报错

### 1.3 数据兼容

- 老台账 `status='done'`：读取正常（`ALL_REQ_STATUSES` 保留）、`statusHistory` 保留原样
- 迁移策略：**不做批量改写**（历史留痕），仅在 UI/查询侧把 done 视为 archived 的前身展示
- `done` 从流程图消失，但已 done 的需求在看板仍有归属（归档泳道）

### 1.4 测试用例

| 用例 | 断言 |
|---|---|
| 新转移 | `accepting → archived` 允许；`accepting → done` 不再允许（invalid_transition） |
| 验收门保留 | 未确认 verification 时 `accepting→archived` 被拒（人工门 + 产物确认） |
| 验收通过落点 | `handleVerifyDecision(pass=true)` → status=archived |
| 归档不再是门 | `done>archived` 不在 HUMAN_ONLY 中；`archive_submit` 在 archived 态可调 |
| 历史兼容 | 载入含 `done` 的台账不丢弃、不报错 |
| 流程图 | `FLOW` 不含 done；各分类 stages 不含 done |
| 提示注入 | 验收通过后绑定会话可见"请准备归档材料" |

## 2. 任务表

见 `reqboard_plan_submit` 的 tasks（t1..t6）。

## 3. 风险与对策

| 风险 | 对策 |
|---|---|
| 移除 done 破坏历史数据可读性 | `ALL_REQ_STATUSES` 保留 done（legacy），单测覆盖老台账载入 |
| 分类档案漏改（bug/doc 等分类的 stages） | 单测遍历 `CATEGORY_FLOW_PROFILES` 断言不含 done |
| 归档材料校验放松 | 校验逻辑不动（只改前置状态），单测覆盖"缺材料仍拒绝" |
| 验收通过即 archived 导致"材料待补"长期挂着 | 看板标记 + 注入提示双保险；材料补齐状态可见 |

## 4. 提交前自查

- [x] 无占位符；任务间依赖明确（t2←t1，t3←t1，t4←t2，t5←t2，t6←t1..t5）
- [x] 四视角齐备（状态机/UI/数据兼容/测试）
- [x] 范围未蔓延（仅流水线简化 + 兼容，不动其他门与校验规则）
