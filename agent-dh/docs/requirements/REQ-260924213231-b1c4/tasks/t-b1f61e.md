# t-b1f61e 立项降级路径不丢文档位置·研发

> 子卡（父卡 t-fbde12 · 阶段 dev） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
立项降级路径不丢文档位置·研发

## 解决什么问题
子卡阶段：研发

## 得到什么结果（验收标准）

本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/create-doc-location.test.ts 全绿；不传 doc_location → 返回 doc_location='docs/requirements/<REQ>/' 且 defaults_used 含 doc_location、台账 docBasePath 同值；传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成；返回 status 与台账一致；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-b1f61e.md

## 实施方案
改 packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts（增 doc_location 入参 + 输出 schema 增 doc_location/defaults_used）、packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts、packages/web/dsh-pmboard/src/application/internal/support.ts（createRequirementDirect 接 docBasePath + 回落标记）；新增 packages/web/dsh-pmboard/tests/create-doc-location.test.ts。

[子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 执行与完工记录
- workflow run：2026-09-25 01:32:58（stopReason=completed，产出非空=True）
- 改动文件：
  - packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts
  - packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts
  - packages/web/dsh-pmboard/src/application/internal/support.ts
  - packages/web/dsh-pmboard/tests/create-doc-location.test.ts
- 完成项：
  - worktree 中 T-10 实施已落盘：CreateTool.ts 的 reqboard_create 增 doc_location 入参，output.schema 增 doc_location/defaults_used（additionalProperties:false 下不缺声明）
  - CreateRequirement.ts 取第四问：resolveDocBasePath(doc_location) → docBasePath 传台账，返回体回填 doc_location/defaults_used 与回落说明 note
  - support.ts：新增 resolveDocBasePath（未传/空串显式回落 CAPTURE_DEFAULTS.docLocation 并标 usedDefault；非字符串/绝对路径/含 .. → REQBOARD_INVALID_INPUT 不静默改路径）+ createRequirementDirect 接 docBasePath 并把回落值写进台账记录（不只留返回体）
  - 回归测试 create-doc-location.test.ts 覆盖 TC-11（不传→回落+defaults_used+台账同值+requirementDocPath 同源）、TC-12（docs/rfcs/→台账与产物路径按它生成）、TC-13（status 与台账一致）、异常流（4 类非法形态拒绝且零写入）、schema 声明；并按 design/test-cases.md 第 9 行补齐文件头 `// serves: FR-7`（此前缺失会被 testFileHasServesHeader 判为孤儿用例）
- 执行段：4 次（末次 2026-09-25 01:29:02，outcome=succeeded）
