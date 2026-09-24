# t-52d7fe 新增 kind=design 登记用例与工具入口·联调

> 子卡（父卡 t-6eca2a · 阶段 integrate） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
新增 kind=design 登记用例与工具入口·联调

## 解决什么问题
子卡阶段：联调

## 得到什么结果（验收标准）
接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-52d7fe-integrate.md，在 filesChanged 中列出该文件

## 实施方案
新增 packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts；改 packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts（SUBMIT_KINDS 增 design + 分派 + schema）与 packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts；新增 packages/web/dsh-pmboard/tests/design-registration.test.ts。

[子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 执行与完工记录
- workflow run：2026-09-24 23:51:39（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-52d7fe-integrate.md
- 完成项：
  - 对 I-1 `reqboard_submit(kind=design)` 做接口联调：用临时探针 tests/__probe-t52d7fe.test.ts（跑完即删）以 defineSubmitTool 真实构造并 execute，逐例比对请求样例/期望响应/实际返回，17/17 verdict=MATCH
  - C1 工具入口接线：parameters.properties.kind.enum 与 SUBMIT_KINDS 均为 requirement/plan/verification/archive/design
  - C2 首次扫 design/ 登记 5 份：{success:true,requirement_id:'REQ-d30001',registered_count:5}，design_docs 5 行 on_disk/registered=true、confirmed=false，台账 5 条，note 指向 reqboard_ask_confirm
  - C3 二次幂等：registered_count=0、台账仍 5 条、5 行 registered 全 true
  - C4 path 单份登记：registered_count=1 且只落 architecture.md
  - C5 登记被闸门读到：assertArtifactGates('design','decomposing').code='artifact_not_confirmed'（不再 missing_artifact）
  - C6 错误语义：REQBOARD_ARTIFACT_NOT_OPENABLE / REQBOARD_FILE_MISSING / REQBOARD_NO_BOUND_REQ 均按契约抛出
  - C7 空目录：success=false、registered_count=0、note 含「未发现可登记的设计文档」、台账 0 条（不谎报成功）
  - 父卡实现测试 design-registration.test.ts 9/9 绿
  - 回归集 7 文件 73 例：2 failed | 71 passed，用基线 HEAD(9e5ebf60) worktree 复跑证明该 2 例为既有失败（FR-2 闸门路径），本卡未引入回归
  - 把联调记录（命令与输出摘要、三方对照表）写入 evidence/t-52d7fe-integrate.md
- 执行段：1 次（末次 2026-09-24 23:49:37，outcome=succeeded）
