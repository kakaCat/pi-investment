# t-4b15cf 新增 kind=design 登记用例与工具入口·测试

> 子卡（父卡 t-6eca2a · 阶段 test） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
新增 kind=design 登记用例与工具入口·测试

## 解决什么问题
子卡阶段：测试

## 得到什么结果（验收标准）
目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4b15cf-test.md，在 filesChanged 中列出该文件

## 实施方案
新增 packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts；改 packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts（SUBMIT_KINDS 增 design + 分派 + schema）与 packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts；新增 packages/web/dsh-pmboard/tests/design-registration.test.ts。

[子卡阶段·测试] 只做本阶段；验收：目标命令输出全绿（贴命令与结果摘要）

## 执行与完工记录
- workflow run：2026-09-24 23:57:00（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-4b15cf-test.md
- 完成项：
  - 在 packages/web/dsh-pmboard 下运行父卡 t-6eca2a（T-3）验收命令 npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts，结果 3 files / 31 tests 全绿，exit 0（本轮为 t-4b15cf 重跑，前次 workflow run 被 cancel）
  - 逐条核对父卡三条业务口径：TC-1 首次 registered_count=5 且 5 条 kind=design 入簿、二次 registered_count=0 幂等、TC-19 前半空目录（design/ 不存在 / 只有非 .md）返回 0 且 success=false 不谎报——均通过
  - 补充锁定（同批用例）：部分新增只数本次新增（第 6 份 registered_count=1）、登记后 G2 由 missing_artifact 转「待确认」、path 单份登记可打开性校验 REQBOARD_ARTIFACT_NOT_OPENABLE / REQBOARD_FILE_MISSING、归属校验 REQBOARD_NO_BOUND_REQ
  - 按测试卡纪律只读不改：确认 4 处实现/用例改动（SubmitDesignArtifacts.ts、SubmitTool.ts +27/−6、prompt.ts +6/−3、design-registration.test.ts，170 行/9 例，头部带 serves FR-1）均为父卡待提交工作区改动，本卡未触碰
  - 把测试记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-4b15cf-test.md（101 行：环境/被测对象/目标命令逐例输出/三条口径核对表/改动归属/结论）
- 执行段：2 次（末次 2026-09-24 23:55:03，outcome=succeeded）
