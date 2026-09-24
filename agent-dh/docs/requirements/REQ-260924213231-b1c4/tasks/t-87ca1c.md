# t-87ca1c 迁移兼容卡与 E2E 复跑·联调

> 子卡（父卡 t-145cb0 · 阶段 integrate） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
迁移兼容卡与 E2E 复跑·联调

## 解决什么问题
子卡阶段：联调

## 得到什么结果（验收标准）
接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-87ca1c-integrate.md，在 filesChanged 中列出该文件

## 实施方案
新增 packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts（复跑设计阶段：落盘 5 份→submit(design)→ask_confirm→move）并回归 packages/web/dsh-pmboard/tests/migration.test.ts（legacy 放行、老需求无 interruption 逐字节兼容）。

[子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 执行与完工记录
- workflow run：2026-09-25 02:16:57（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-87ca1c-integrate.md
- 完成项：
  - 对本卡涉及接口/接缝做联调并逐例给出请求样例、期望响应、实际返回：I-1 reqboard_submit(kind=design)、I-3 reqboard_ask_confirm(target=artifact,kind=design)、I-9/E-3/E-8 闸门拒绝码（MISSING_ARTIFACT / ARTIFACT_NOT_CONFIRMED）、迁移兼容 migrate-ledger v4→v7、FR-6 续跑输入包 legacy 兼容
  - 8/8 例 MATCH（请求/期望/实际三者逐字段一致，PROBE_TOTAL=8 MATCH=8 MISMATCH=0）；探针 tests/__probe-t87ca1c.test.ts 跑完即删，工作区无残留
  - 父卡 T-13 目标命令 3 文件 / 25 用例全绿（e2e-design-handoff 5 + migration 9 + consistency 11，exit 0）
  - 全量回归对照 D-1 基线：仍为 6 文件 / 7 例红，其中 5 文件均为基线已登记红、design-completeness-gate 与 size-budget 两项基线红已转绿；唯一新增红 language-layer.test.ts（F-1，归 T-8，非本卡范围）已在证据中如实登记并交出
  - 把联调记录（命令与输出摘要、失败集合对照、类型基线、发现项）写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-87ca1c-integrate.md
- 执行段：2 次（末次 2026-09-25 02:15:38，outcome=succeeded）
