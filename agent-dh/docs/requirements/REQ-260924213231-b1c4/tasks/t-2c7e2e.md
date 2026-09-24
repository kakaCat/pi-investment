# t-2c7e2e 设计提示词写明登记命令·测试

> 子卡（父卡 t-216224 · 阶段 test） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
设计提示词写明登记命令·测试

## 解决什么问题
子卡阶段：测试

## 得到什么结果（验收标准）
目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-2c7e2e-test.md，在 filesChanged 中列出该文件

## 实施方案
改 packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md 与 packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md（覆盖条目 1 写明登记命令+触发者+不要猜 kind），重跑生成器刷新 packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts；新增 packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts。

[子卡阶段·测试] 只做本阶段；验收：目标命令输出全绿（贴命令与结果摘要）

## 执行与完工记录
- workflow run：2026-09-25 01:00:31（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-2c7e2e-test.md
- 完成项：
  - 运行父卡目标命令并确认全绿：① node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs → exit 0；② npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts → 2 files / 25 tests 通过，exit 0
  - 逐条核对父卡三条业务口径：design/light 与 heavy 注入文本含 reqboard_submit(kind=design)+触发者「agent 自己」+「不要猜 kind」；不含「落盘即产物/目录自动发现登记」旧断言（全 prompt 源树 grep 0 命中）；已由 10 例新用例锁定通过
  - 补充回归 prompt-baseline + prompt-gates + stage-prompts → 3 files / 65 tests 全绿，未因提示词文本变更回归
  - 核验改动归属：T-8 四文件（light/heavy overrides、generated/fragments.ts、P1 基线）+ 新增用例均为父卡待提交改动，本卡只读不改；本轮新增产物仅本测试记录
  - 把本轮测试记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-2c7e2e-test.md（139 行）
- 执行段：1 次（末次 2026-09-25 00:58:38，outcome=succeeded）
