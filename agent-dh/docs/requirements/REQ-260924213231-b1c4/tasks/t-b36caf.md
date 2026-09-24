# t-b36caf 组合根瘦身使尺寸门禁转绿·测试

> 子卡（父卡 t-800d53 · 阶段 test） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
组合根瘦身使尺寸门禁转绿·测试

## 解决什么问题
子卡阶段：测试

## 得到什么结果（验收标准）
目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b36caf-test.md，在 filesChanged 中列出该文件

## 实施方案
把配置/路径纯函数与捕获根装配从 packages/web/dsh-pmboard/src/index.ts 抽到新增 packages/web/dsh-pmboard/src/plugin-config.ts 与 packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts；index.ts 再导出 dshHomePath/nodeIsolationEnabled 保兼容。

[子卡阶段·测试] 只做本阶段；验收：目标命令输出全绿（贴命令与结果摘要）

## 执行与完工记录
- workflow run：2026-09-25 02:02:59（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-b36caf-test.md
- 完成项：
  - 复跑父卡 t-800d53（T-12）目标命令：npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts → 3 files / 60 tests 全绿（exit 0）
  - 核验尺寸门禁：wc -l packages/web/dsh-pmboard/src/index.ts = 357 ≤ 400，且 size-budget 门禁对 src/**/*.ts 全量扫描亦绿
  - 核验兼容性：nodeIsolationEnabled/dshHomePath 由 src/index.ts:73 再导出，tests/isolate-node-context.test.ts:38 仍从 '../src/index.js' import 且优先级行为 9 例断言不变
  - 在 evidence 目录写入测试记录 t-b36caf-test.md（73 行，含目标命令原文与实际输出、行数核对、兼容再导出核对与验收口径对照表）
- 执行段：1 次（末次 2026-09-25 02:02:16，outcome=succeeded）
