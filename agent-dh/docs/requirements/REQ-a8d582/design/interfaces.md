# REQ-a8d582 设计·接口契约

> requirement_refs: FR-1, FR-2, FR-3, FR-4
> 上游：[requirement.md](../requirement.md) · 关联：[architecture.md](./architecture.md)

## 1. POST /dashboard/api/reqboard/req/verify/pass serves: FR-1, FR-4

| 项 | 内容 |
|---|---|
| 调用方 | 看板（浏览器，仅人操作）；agent 不调用 |
| 入参 | `id: string`（需求 id，必填）；`note?: string`（可选，进审核意见）；**新增** `confirm_override?: string`（覆盖说明） |
| 行为 | 无不合格且材料齐全 → 与现状一致；否则要求 `confirm_override` 非空 |
| 返回 | 成功：需求记录（`status=archived`；覆盖通过时含 `acceptanceOverride`）；失败：见 §5 |
| 兼容 | 不传 `confirm_override` 的老调用方在"无不合格且材料齐全"时行为不变；其余情形被拒绝（这正是本次要的收紧） |

## 2. POST /dashboard/api/reqboard/req/verdicts serves: FR-2

| 项 | 内容 |
|---|---|
| 入参 | 不变：`id` / `version` / `verdicts[]`（itemId、status、opinion） |
| **行为变更** | 有 `failed` 项时**不再**改需求状态、**不再**建返工任务；只写验收单 |
| 返回 | 既有字段保留（passed/failed/pending/sheet_version）；`rework_tasks` 在本次语义下恒为空数组；`note` 文案改为指向"退回返工" |
| 兼容 | 依赖"自动打回"的调用方需改为显式调 `/req/verify/rework`（看板按钮已提供） |

## 3. POST /dashboard/api/reqboard/req/verify/rework serves: FR-2

| 项 | 内容 |
|---|---|
| 入参 | 不变：`id`、`note`（必填，退回意见） |
| **行为补强** | 置 `implementing` 之前，按当前验收单的 `failed` 项批量建返工任务（数量 = failed 项数） |
| 返回 | 需求记录；新建任务随之出现在任务列表 |
| 幂等 | 状态已不在验收态时按既有前置拒绝（`badInput`），不会二次建卡 |

## 4. 客户端交互契约 serves: FR-1, FR-3

- **按钮可见性**：`req.status === 'accepting'` 即渲染 `data-action="verify-pass"`；不再以 `req.verification !== undefined` 为条件，也不再渲染"…才会出现「验收通过」"的提示。
- **点击流程**：装配确认文案 → `window.confirm` → false 直接返回（零副作用）→ true 调 `verifyPass` 并在成功后 `fetchAll()` 刷新。
- **失败处理**：沿用既有 `window.alert(String(e))`，把后端可读文案原样露出。

## 5. 错误码 serves: FR-4

| 错误码 | 触发条件 | 文案要点 |
|---|---|---|
| `verify_override_required` | 有不合格项或未交材料，且 `confirm_override` 为空 | 含"不通过 N 项 / 未裁决 M 项"或"尚无验收材料"，并说明需人再次确认 |
| `missing_artifact` | 材料齐全但 verification 产物未登记（现状保留） | 仅在非覆盖路径触发 |
| 既有 `badInput` 系列 | 状态不在验收态 / 需求不存在 | 维持现状 |
