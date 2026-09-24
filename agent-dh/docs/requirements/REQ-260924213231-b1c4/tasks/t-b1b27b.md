# t-b1b27b 立项降级路径不丢文档位置·测试

> 子卡（父卡 t-fbde12 · 阶段 test） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
立项降级路径不丢文档位置·测试

## 解决什么问题
子卡阶段：测试

## 得到什么结果（验收标准）
目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b1b27b-test.md，在 filesChanged 中列出该文件

## 实施方案
改 packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts（增 doc_location 入参 + 输出 schema 增 doc_location/defaults_used）、packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts、packages/web/dsh-pmboard/src/application/internal/support.ts（createRequirementDirect 接 docBasePath + 回落标记）；新增 packages/web/dsh-pmboard/tests/create-doc-location.test.ts。

[子卡阶段·测试] 只做本阶段；验收：目标命令输出全绿（贴命令与结果摘要）

## 执行与完工记录
- workflow run：2026-09-25 01:39:48（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-b1b27b-test.md
- 完成项：
  - 执行父卡验收命令 npx vitest run tests/create-doc-location.test.ts（工作目录 packages/web/dsh-pmboard）——1 file / 5 tests 全绿，exit 0
  - 补充回归 output-contract + tools-schema + tools-dispatch 3 files / 28 tests 全绿，exit 0，T-10 新增返回键无契约/Schema 回归
  - 逐条核对父卡三条业务口径：不传 doc_location → 返回默认值且 defaults_used 含 doc_location、台账 docBasePath 同值；传 docs/rfcs/ → 台账与产物路径按它生成；返回 status 与台账一致（另覆盖非法路径 REQBOARD_INVALID_INPUT 且零写台账）
  - 采集环境与改动归属：HEAD=9e5ebf60、node v22.23.2、vitest 2.1.9；numstat support.ts 44/1、CreateRequirement.ts 17/2、CreateTool.ts 11/0，测试文件 untracked；本卡只读不改
  - 把测试记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-b1b27b-test.md（含命令原文、逐例输出、口径对照表、回归、改动归属、结论）
- 执行段：1 次（末次 2026-09-25 01:38:24，outcome=succeeded）
