# t-5b02db 设计提示词写明登记命令·研发

> 子卡（父卡 t-216224 · 阶段 dev） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
设计提示词写明登记命令·研发

## 解决什么问题
子卡阶段：研发

## 得到什么结果（验收标准）

本卡为该父卡的研发子卡，交付物 = 父卡验收口径：node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs 退出 0；npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts 全绿；design/light 与 heavy 文本含 reqboard_submit(kind=design)，且不含「落盘即产物」旧断言；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-5b02db.md

## 实施方案
改 packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md 与 packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md（覆盖条目 1 写明登记命令+触发者+不要猜 kind），重跑生成器刷新 packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts；新增 packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts。

[子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 执行与完工记录
- workflow run：2026-09-25 00:53:50（stopReason=completed，产出非空=True）
- 改动文件：
  - packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md
  - packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md
  - packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts
  - packages/web/dsh-pmboard/tests/fixtures/stage-prompts-baseline-p1.json
  - packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts
- 完成项：
  - design/light/overrides.md 覆盖条目 1 改写为「登记命令与触发者（不要猜 kind）」：写明文档落盘后由本窗口 agent 自己调 reqboard_submit(kind=design)（缺省扫 design/ 全目录、幂等），点名 requirement/plan/verification/archive 属别的阶段产物、传错必被拒，登记齐后调 reqboard_ask_confirm(target=artifact, kind=design)；删除旧「落盘即产物」断言（原文无该词，改为明写「登记不是自动发生的」）。
  - design/heavy/overrides.md 覆盖条目 1 同样改写：登记命令 + 触发者（本窗口 agent，不等人打开看板）+「不要猜 kind」+ 旧版本无入口时打开看板需求详情页触发的回落说明；删除「设计文档落盘即产物（目录自动发现登记）」。
  - 重跑 scripts/inline-prompt-fragments.mjs 刷新 generated/fragments.ts（128 fragments / 72197 bytes）。
  - 重跑 scripts/dump-stage-prompts.mjs 刷新 P1 基线快照，diff 仅 design/light 与 design/heavy 两键，使 tests/prompt-baseline.test.ts 与改动后的注入文本逐字一致（FR-5 要求的基线快照更新）。
  - 新增 tests/design-prompt-registration.test.ts（头部 serves: FR-5）：TC-10 断言 design/light 与 design/heavy 注入文本（含六类型档路由壳）含 reqboard_submit(kind=design)、触发者「agent 自己」、「不要猜 kind」，且不含「落盘即产物 / 目录自动发现登记」旧断言；TC-17 故障注入回归断言提示词改动未放松拆分内容硬门禁（depends_on 表头仍拒 design_contains_decomposition）。
- 执行段：1 次（末次 2026-09-25 00:51:07，outcome=succeeded）
