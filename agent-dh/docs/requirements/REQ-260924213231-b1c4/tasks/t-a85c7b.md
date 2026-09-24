# t-a85c7b 实现断点常驻与续跑输入包·测试

> 子卡（父卡 t-7b5e7a · 阶段 test） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
实现断点常驻与续跑输入包·测试

## 解决什么问题
子卡阶段：测试

## 得到什么结果（验收标准）
目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a85c7b-test.md，在 filesChanged 中列出该文件

## 实施方案
新增 packages/web/dsh-pmboard/src/application/internal/interruption.ts、packages/web/dsh-pmboard/src/application/use-cases/NoteInterruption.ts、packages/web/dsh-pmboard/src/tools/NoteInterruptionTool/NoteInterruptionTool.ts；改 packages/web/dsh-pmboard/src/adapters/CaptureHook.ts（onTurnFinished 信号）、packages/web/dsh-pmboard/src/application/internal/node-input-package.ts（## 断点节）、packages/web/dsh-pmboard/src/application/use-cases/SubmitArtifact.ts、packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts、packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts、packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts、packages/web/dsh-pmboard/src/application/use-cases/AcceptSheet.ts、packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts（stampCheckpoint）、packages/web/dsh-pmboard/src/index.ts（异步边界接线+注册）；新增 packages/web/dsh-pmboard/tests/interruption-checkpoint.test.ts。

[子卡阶段·测试] 只做本阶段；验收：目标命令输出全绿（贴命令与结果摘要）

## 执行与完工记录
- workflow run：2026-09-25 01:20:01（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-a85c7b-test.md
- 完成项：
  - 执行目标命令 npx vitest run tests/interruption-checkpoint.test.ts（工作目录 packages/web/dsh-pmboard）：1 file / 15 tests 全绿，exit 0
  - 逐条核对验收四口径并记录断言落点：只交棒→reason=checkpoint 且 pendingAction 非空（:40-52）；turn/end error→reason=error:UPSTREAM_STREAM_IDLE:stream idle 3m（:103-115）；重建输入含『## 断点』+pendingAction 四要素（:193-211）；老需求无字段→输入包逐字节不变（:213-221）
  - 层边界守护核验：新增 application 文件（interruption.ts / NoteInterruption.ts）grep node:/adapters import 均为 NONE；layer-boundary.test.ts 唯一失败为 diag-log.ts 存量基线（HEAD 9e5ebf60 即存在），非本卡引入
  - 接线回归护栏：capture-hook / tools-dispatch / apply-wiring 全绿（42 例通过），T-9 改动直接消费方无回归
  - 改动面核验：本卡只读，未修改任何实现/适配器/测试源码；本轮新增产物仅测试记录文件
  - 把测试记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a85c7b-test.md（含命令、逐例输出、diffstat、结论）
- 执行段：1 次（末次 2026-09-25 01:19:13，outcome=succeeded）
