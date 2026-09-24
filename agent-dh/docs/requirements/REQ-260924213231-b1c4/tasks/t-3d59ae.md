# t-3d59ae pm 弹框统一来源标志·复核

> 子卡（父卡 t-9f96a1 · 阶段 review） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
pm 弹框统一来源标志·复核

## 解决什么问题
子卡阶段：复核

## 得到什么结果（验收标准）
复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-3d59ae-review.md，在 filesChanged 中列出该文件

## 实施方案
新增 packages/web/dsh-pmboard/src/domain/text/pm-badge.ts（pmHeader）；改 packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts、packages/web/dsh-pmboard/src/application/use-cases/AcceptSheet.ts、packages/web/dsh-pmboard/src/application/internal/capture-mapping.ts、packages/web/dsh-pmboard/src/application/use-cases/HandleFailure.ts 四处 header 走 pmHeader；新增 packages/web/dsh-pmboard/tests/pm-question-badge.test.ts。

[子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 执行与完工记录
- workflow run：2026-09-25 01:52:25（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-3d59ae-review.md
- 完成项：
  - 设计基线逐条比对（FR-8 / I-7 / UC-5 / TC-14 / architecture L53,L107 / test-cases L9 头部约定 / decomposition T-11 行）：R1~R12 共 12 条结论逐条给出，11 条显式「无偏离」+ 依据，1 条「有偏离」（D-A）
  - 独立复跑父卡验收命令：npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts → 3 文件 38/38 绿、exit 0（与上游自述一致）
  - 关联回归 9 文件 75/76（唯一红 size-budget.test.ts，归因 O-2，非本卡）；全量套件 7 文件/8 例红，对比 D-1 基线 7 文件/9 例：design-completeness-gate 2 例已修绿、新增 language-layer 1 例（归 T-8）——本卡无任何新增红
  - 类型检查 tsc --noEmit 24 条（23 条 D-1 基线 + T-6 已知第 24 条），本卡 6 文件命中 0 条（增量 0，符合 T-10/D-1 口径）
  - 一次性探针独立见证（真用例捕 header + 源码穷举 + 孤儿用例读数，运行后已删除）：四处构造点 9 条 header 全带「📋 PM · 」；questions.ask( 站点恰 4 个、无遗漏；正文原样透传
  - D-A（有偏离·低严重度·不阻断）：tests/pm-question-badge.test.ts 头部 20 行缺 serves: FR-8 声明，被本需求自己的孤儿检查 testFileHasServesHeader 判为「缺映射」，验收单会追加一条警告级 pending 项；建议一行补记（本卡只读未改）
  - O-1 计划落点漏记自动适配：tests/auto-chain-approval.test.ts（+1 import pmHeader、1 断言改 pmHeader('确认')），属必要连带修改
  - O-2 size-budget 2 红：index.ts=458（D-1/D-2 已知、T-12 范围）与 Decompose.ts=401（HEAD 恰 400，由 T-9 的 stampCheckpoint 单行推过阈值）——均非本卡
  - O-3 落点表 11 文件中 4 个缺 serves 声明（含本卡 pm-question-badge）+ e2e-design-handoff.test.ts 尚未落盘（T-13），跨卡登记
  - O-4 全量套件新增 1 红 language-layer.test.ts（T-8 改 design/light/overrides.md 措辞致既有断言失配），归 T-8
  - O-5 措辞级观察：pm-badge.ts 注释「agent 伪造不了」过度承诺——pm 无法拦截 agent 在宿主提问正文手写假前缀，属设计边界（§5 不改宿主包），非实现缺陷
  - 复核记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-3d59ae-review.md（270 行）；本卡只读，未修改任何实现/测试/配置源码
  - 复核结论：通过（卡面验收达标）；附 1 项低严重度约定偏离 + 5 项观察项，均不阻塞父卡收尾
- 执行段：1 次（末次 2026-09-25 01:46:47，outcome=succeeded）
