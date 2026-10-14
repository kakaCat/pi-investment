# 归档结论（REQ-261007101318-c392 盯盘触发：休市日闸门缺失 + 通知缺股票名称）

> 归档目录：`docs/requirements/REQ-261007101318-c392` ｜ 类型：feature
> 渲染时刻：2026-10-07T06:05:06.566Z（由归档提交注入）

## 一句话结论

盯盘通知四条硬契约落地：非交易日零事件（tick 与 run_forever 同口径 + 跳过留痕）、名称缺失不回落成代码、级别与闭环承诺解耦、外发可归因（quant.notification_audit 一通知一行 + 卡面 v2-watch@host#pid 尾注）。认知并进 L1 说明书（认知 14）与 L2 页 watch-notification-contract.md。

## 合并去向

- `docs/architecture/watch-notification-contract.md` — ✅ 存在 6579 字节（生效根 /Users/mac/Documents/ai/pi-investment/quantsys-v2，判据来源 by=project-id）
- `docs/architecture/project-manual.md` — ✅ 存在 13233 字节（生效根 /Users/mac/Documents/ai/pi-investment/quantsys-v2，判据来源 by=project-id）
- `docs/architecture/watch-rules.md` — ✅ 存在 7549 字节（生效根 /Users/mac/Documents/ai/pi-investment/quantsys-v2，判据来源 by=project-id）

## 人读材料

清单 12 份 · 对照机器产物 3 类 / 31 份（按 kind 分组）：

**requirement**（1 份）
- `docs/requirements/REQ-261007101318-c392/requirement.md`

**plan**（1 份）
- `docs/requirements/REQ-261007101318-c392/decomposition.md`

**verification**（1 份）
- `docs/requirements/REQ-261007101318-c392/verification.md`

**notes**（9 份）
- `docs/requirements/REQ-261007101318-c392/notes/t6-receipt-rehearsal.md`
- `docs/requirements/REQ-261007101318-c392/reviews/code-review.md`
- `docs/requirements/REQ-261007101318-c392/tests/evidence.md`
- `docs/requirements/REQ-261007101318-c392/design/architecture.md`
- `docs/requirements/REQ-261007101318-c392/design/data-model.md`
- `docs/requirements/REQ-261007101318-c392/design/interfaces.md`
- `docs/requirements/REQ-261007101318-c392/design/test-cases.md`
- `docs/requirements/REQ-261007101318-c392/design/use-cases.md`
- `docs/requirements/REQ-261007101318-c392/archive.md`

## 机器产物（可重建，折叠）

已折叠 3 类 / 31 份 · 共 270636 字节（逐文件不铺开；原文件位置与数量不变）：
- 追溯报告（rtm-*.yml） · 6 个 · 64012 字节
- 追溯报告目录（rtm-*/） · 24 个 · 38235 字节
- 台账镜像（queue.json） · 1 个 · 168389 字节
  - 摘要：任务 24 · 依赖边 20 · 就绪 0 · 生成时间 2026-10-07T05:41:28.868Z · 168389 字节

## 说明书更新点

- `docs/architecture/watch-notification-contract.md#4-外发审计-每次外发可归因到发送方` — 新建 L2 页：盯盘通知四条契约一次写清——开市闸门判据、名称解析链与「名称缺失」语义、级别与闭环解耦、外发审计与来源标识、卡面内容契约、已知瑕疵与后续
- `docs/architecture/project-manual.md#3-关键认知-读到就少踩一次` — 新增认知 14「盯盘通知有四条硬契约」：非交易日零事件 / 名称不回落 / 级别与闭环解耦 / 外发可归因
- `docs/architecture/project-manual.md#4-最近更新-每次-l1-变更追加一行` — 追加 2026-10-07 一行（认知 14 + 新建 L2 页 + quant.notification_audit 上线）；另在 docs/README.md 新增架构入口段（项目文档索引维护）
- `docs/architecture/watch-rules.md#版本历史` — 追加 2026-10-07 一行指向通知契约页：本页只管「条件怎么写」，不管「什么时候发、长什么样、谁发的」

## 相关

- 需求：`REQ-261007101318-c392`（feature）
- 归档目录：`docs/requirements/REQ-261007101318-c392`
- 渲染时刻：2026-10-07T06:05:06.566Z（归档材料提交时刻的渲染读数）
- 本文件是**渲染物，不是事实源**：内容一律由归档提交派生（FR-5 边界 3）。
