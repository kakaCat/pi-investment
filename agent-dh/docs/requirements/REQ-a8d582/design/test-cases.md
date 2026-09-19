# REQ-a8d582 设计·测试用例

> requirement_refs: FR-1, FR-2, FR-3, FR-4
> 上游：[requirement.md](../requirement.md) · 关联：[interfaces.md](./interfaces.md)

## 1. 用例清单 serves: FR-1, FR-2, FR-3, FR-4

| # | 验什么 | 对应编号 | 怎么验 | 预期 | 实际文件 |
|---|---|---|---|---|---|
| TC-1 | 验收态未交材料也出按钮 | FR-3 | 断言 `renderActionBar` 输出 | 操作条含 `data-action="verify-pass"`，且不含"才会出现「验收通过」"文案 | tests/board-info-fixes.test.ts |
| TC-2 | 确认文案含计数 | FR-1 | 构造 1 failed + 1 pending 的需求，断言装配函数输出 | 文案含"不通过 1 / 未裁决 1"与"覆盖通过"字样 | tests/board-info-fixes.test.ts |
| TC-3 | 裁决不改状态 | FR-2 | `POST /req/verdicts` 带 1 项 failed | 需求仍返回 `accepting`、任务总数不变、note 指向"退回返工" | tests/verdicts-and-rework.test.ts |
| TC-4 | 退回返工才建卡 | FR-2 | 接着调 `POST /req/verify/rework`（带 note） | 需求 `implementing`；新增任务数 = failed 项数；卡含验收意见 | tests/verdicts-and-rework.test.ts |
| TC-5 | 覆盖必填原因 | FR-4 | 有 failed 且不带 `confirm_override` 调 pass | 400 + `verify_override_required`；状态不变 | tests/verify-override.test.ts |
| TC-6 | 覆盖通过落痕 | FR-4 | 带 `confirm_override` 再调一次 | `archived`；`acceptanceOverride` 含 at/by/detail/failed/pending/noMaterials；评论与状态事件可见原文 | tests/verify-override.test.ts |
| TC-7 | 无材料覆盖通过 | FR-4 | 验收态无 verification，带 `confirm_override` 调 pass | `archived`，不报 `missing_artifact` | tests/verify-override.test.ts |
| TC-8 | 不回归 | FR-1 | 全过且材料齐全，不带 `confirm_override` 调 pass | 正常 `archived`，无 400 | tests/verify-override.test.ts |
| TC-9 | 端到端链路 | FR-1, FR-4 | 跨层全链路：裁决不通过仍在验收态 → 看板文案装配 → 覆盖通过 → 台账 → 客户端重渲染 | 最终 `archived`、三处留痕一致、按钮消失 | tests/e2e-accept-override.test.ts |

## 2. 既有用例的更新 serves: FR-3

- `tests/board-info-fixes.test.ts`：「验收态尚未交材料…不给 verify-pass」这条断言方向**反转**（现在必须给）。
- `tests/verdicts-and-rework.test.ts`：自动打回的断言改为"状态不变 + 指引 note"。
- `tests/acceptance-archive.test.ts`：若有依赖"自动打回"的前置，改为显式调 rework。

## 3. 验证命令 serves: FR-1, FR-2, FR-3, FR-4

```bash
cd agent-dh/packages/pages/dsh-pmboard
pnpm build            # 改 src/ 后必须重建 client 产物（构建新鲜度门）
npx vitest run        # 全量单测
python3 ../../../scripts/relink-profile.py --check   # profile 符号链接未漂移
```

## 4. 端到端场景 serves: FR-1, FR-2, FR-3, FR-4

本需求改的是"人点按钮 → HTTP → 台账 → 看板刷新"的完整链路，跨 client 与 server 两端，**属于多组件串联**，因此必须有一条端到端用例（TC-9），不能只交单元/集成测试。E2E 路径：建需求 → 提交验收材料（含 1 项不通过裁决）→ 断言仍在验收态 → 覆盖通过 → 断言 `archived` 且 `verification.override` 与评论、状态事件三处一致。
