# t-d76da9 新增 kind=design 登记用例与工具入口·复核

> 子卡（父卡 t-6eca2a · 阶段 review） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
新增 kind=design 登记用例与工具入口·复核

## 解决什么问题
子卡阶段：复核

## 得到什么结果（验收标准）
复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-d76da9-review.md，在 filesChanged 中列出该文件

## 实施方案
新增 packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts；改 packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts（SUBMIT_KINDS 增 design + 分派 + schema）与 packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts；新增 packages/web/dsh-pmboard/tests/design-registration.test.ts。

[子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 执行与完工记录
- workflow run：2026-09-24 23:54:27（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-d76da9-review.md
- 完成项：
  - 复核记录落盘 docs/requirements/REQ-260924213231-b1c4/evidence/t-d76da9-review.md（159 行，含逐条对照 17/17、独立复现、偏离清单、观察、结论、给父卡的非阻断行动建议）
  - 逐条给出设计↔实现复核结论：17 项设计/卡面约定核对为「无偏离」并附实测依据（I-1 入参/schema enum/分派表/落点/归属校验/path 语义/幂等/design_docs 七字段/空目录不谎报/E-1,E-2 错误码/G2 可读/提示词/唯一发现核心/不改既有契约/无阶段门/验收与类型面）
  - 识别 3 处非阻断项：M-1 输出 schema 的 conditional 声明为 string 宽于设计的 'frontend'|'backend' 联合；M-2 投影 designDocNames（扁平、不跳点文件）与发现核心（递归、跳点文件）口径不一致，隐藏件报 on_disk=true/registered=false、嵌套 design/sub/*.md 被登记却不在 design_docs[]；M-3 tools-dispatch.test.ts:38 注释仍写「四类」且未把 design 纳入分派断言
  - 记录 5 条复核观察：O-1 design 分支由运行态测试覆盖、O-2 on_disk 行集=必交∪磁盘件（非偏离）、O-3 缺省扫描与 design/ 等价、O-4 跨卡依赖 design-docs.ts（T-4 落点）、O-5 mutate 结果未复查（实际不触发）
  - 临时探针 tests/__probe-t-d76da9.test.ts 已在本轮内删除，glob 校验无残留；未修改任何实现或测试源码
- 执行段：1 次（末次 2026-09-24 23:51:39，outcome=succeeded）
