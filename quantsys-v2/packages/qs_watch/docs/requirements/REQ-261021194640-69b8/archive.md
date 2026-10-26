# 归档结论（REQ-261021194640-69b8 盯盘执行闭环三接缝：成交回写·消息投递·待办闭环）

> 归档目录：`docs/requirements/REQ-261021194640-69b8` ｜ 类型：feature
> 渲染时刻：2026-10-21T13:44:08.730Z（由归档提交注入）

## 一句话结论

盯盘执行闭环三接缝落地：成交回写收敛待办、critical 消息建 P1 待办、关闭接规则联动；agent 下单终判不变。

## 合并去向

- `docs/guides/watch-exec-loop.md` — ✅ 存在 2604 字节（生效根 /Users/yunpeng/pi-investment/quantsys-v2/packages/qs_watch，判据来源 by=project-id）

## 人读材料

清单 49 份 · 对照机器产物 3 类 / 40 份（按 kind 分组）：

**requirement**（1 份）
- `docs/requirements/REQ-261021194640-69b8/requirement.md`

**plan**（1 份）
- `docs/requirements/REQ-261021194640-69b8/decomposition.md`

**verification**（1 份）
- `docs/requirements/REQ-261021194640-69b8/verification.md`

**retro**（1 份）
- `docs/requirements/REQ-261021194640-69b8/reviews/review-report.md`

**notes**（45 份）
- `docs/requirements/REQ-261021194640-69b8/tests/test-evidence.md`
- `docs/requirements/REQ-261021194640-69b8/verification-evidence.md`
- `docs/requirements/REQ-261021194640-69b8/advance-log.md`
- `docs/requirements/REQ-261021194640-69b8/design/architecture.md`
- `docs/requirements/REQ-261021194640-69b8/design/backend.md`
- `docs/requirements/REQ-261021194640-69b8/design/data-model.md`
- `docs/requirements/REQ-261021194640-69b8/design/interfaces.md`
- `docs/requirements/REQ-261021194640-69b8/design/test-cases.md`
- `docs/requirements/REQ-261021194640-69b8/design/use-cases.md`
- `docs/requirements/REQ-261021194640-69b8/prototypes/INDEX.md`
- `docs/requirements/REQ-261021194640-69b8/prototypes/detail.html`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-c6c5d2.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-0846ee.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-c18a41.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-e95a2a.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-e29f67.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-a5fa64.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-27e8c7.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-b8d5ae.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-88d4da.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-3ef50b.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-2ff7ca.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-e416b7.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-f9a9b3.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-1c3597.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-f2474a.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-e1eb49.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-7e4e44.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-947421.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-902bf1.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-c1ce88.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-2932b9.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-552104.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-c41448.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-ec9d80.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-66833a.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-da557b.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-46c354.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-91a8b2.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-eb06ad.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-c573f5.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-a8d1da.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-7d1677.md`
- `docs/requirements/REQ-261021194640-69b8/tasks/t-627a70.md`
- `docs/requirements/REQ-261021194640-69b8/archive.md`

## 机器产物（可重建，折叠）

已折叠 3 类 / 40 份 · 共 472853 字节（逐文件不铺开；原文件位置与数量不变）：
- 追溯报告（rtm-*.yml） · 6 个 · 203979 字节
- 追溯报告目录（rtm-*/） · 33 个 · 40610 字节
- 台账镜像（queue.json） · 1 个 · 228264 字节
  - 摘要：任务 33 · 依赖边 31 · 就绪 0 · 生成时间 2026-10-21T12:08:54.047Z · 228264 字节

## 说明书更新点

- `docs/guides/watch-exec-loop.md#exec-loop` — 补充三条接缝的边界与失败语义、执行待办状态口径（含期限按库端 created_at）、统计与盘后窗口，以及 evidence 迁移与回滚方式

## 相关

- 需求：`REQ-261021194640-69b8`（feature）
- 归档目录：`docs/requirements/REQ-261021194640-69b8`
- 渲染时刻：2026-10-21T13:44:08.730Z（归档材料提交时刻的渲染读数）
- 本文件是**渲染物，不是事实源**：内容一律由归档提交派生（FR-5 边界 3）。
