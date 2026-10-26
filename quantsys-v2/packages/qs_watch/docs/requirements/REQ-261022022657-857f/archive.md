# 归档结论（REQ-261022022657-857f 交易闭环补口：反思唤醒 + 减仓批次收敛 + 消息→离场）

> 归档目录：`docs/requirements/REQ-261022022657-857f` ｜ 类型：feature
> 渲染时刻：2026-10-21T18:47:53.220Z（由归档提交注入）

## 一句话结论

交易闭环三处接线补齐：盘后反思经既有 notify_agent→/wake 真正唤醒 agent；减仓部分成交按累计比例逐批退役规则并写 fill 事件（幂等+降级）；消息→离场核实为既有 69b8 实现并补回归；metrics 增两个当日读数（缺数 null）。

## 合并去向

- `docs/guides/trading-plan.md` — ✅ 存在 4211 字节（生效根 /Users/yunpeng/pi-investment/quantsys-v2/packages/qs_watch，判据来源 by=project-id）
- `docs/architecture/project-manual.md` — ✅ 存在 2520 字节（生效根 /Users/yunpeng/pi-investment/quantsys-v2/packages/qs_watch，判据来源 by=project-id）

## 人读材料

清单 38 份 · 对照机器产物 3 类 / 31 份（按 kind 分组）：

**requirement**（1 份）
- `docs/requirements/REQ-261022022657-857f/requirement.md`

**plan**（1 份）
- `docs/requirements/REQ-261022022657-857f/decomposition.md`

**verification**（1 份）
- `docs/requirements/REQ-261022022657-857f/verification.md`

**notes**（35 份）
- `docs/requirements/REQ-261022022657-857f/design/architecture.md`
- `docs/requirements/REQ-261022022657-857f/design/data-model.md`
- `docs/requirements/REQ-261022022657-857f/design/interfaces.md`
- `docs/requirements/REQ-261022022657-857f/design/test-cases.md`
- `docs/requirements/REQ-261022022657-857f/design/use-cases.md`
- `docs/requirements/REQ-261022022657-857f/design/backend.md`
- `docs/requirements/REQ-261022022657-857f/reviews/review-notes.md`
- `docs/requirements/REQ-261022022657-857f/tests/test-evidence.md`
- `docs/requirements/REQ-261022022657-857f/advance-log.md`
- `docs/requirements/REQ-261022022657-857f/prototypes/INDEX.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-e12dcf.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-e481c3.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-558de7.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-a5fbed.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-b65fd2.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-eec5ea.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-887e9b.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-4b43e8.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-c0b38b.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-6d5405.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-4c1d31.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-1088bf.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-1b778c.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-ebde4d.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-4d4ec2.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-46d7fb.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-077bfc.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-a779d3.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-d2e75b.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-35badf.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-c02f99.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-e5df78.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-f9b1f4.md`
- `docs/requirements/REQ-261022022657-857f/tasks/t-08f77b.md`
- `docs/requirements/REQ-261022022657-857f/archive.md`

## 机器产物（可重建，折叠）

已折叠 3 类 / 31 份 · 共 281980 字节（逐文件不铺开；原文件位置与数量不变）：
- 追溯报告（rtm-*.yml） · 6 个 · 90578 字节
- 追溯报告目录（rtm-*/） · 24 个 · 33437 字节
- 台账镜像（queue.json） · 1 个 · 157965 字节
  - 摘要：任务 24 · 依赖边 22 · 就绪 0 · 生成时间 2026-10-21T18:31:37.365Z · 157965 字节

## 说明书更新点

- `docs/architecture/project-manual.md#交易计划与反思闭环` — 新增闭环接线段：反思唤醒、批次退役与 fill 事件、消息待办、metrics 两个当日读数及其缺数语义

## 相关

- 需求：`REQ-261022022657-857f`（feature）
- 归档目录：`docs/requirements/REQ-261022022657-857f`
- 渲染时刻：2026-10-21T18:47:53.220Z（归档材料提交时刻的渲染读数）
- 本文件是**渲染物，不是事实源**：内容一律由归档提交派生（FR-5 边界 3）。
