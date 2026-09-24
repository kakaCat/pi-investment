# t-9d9cf9 兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：review
- 端侧：fullstack

## 得到什么结果
①grep -rn "'需求文档'" src 映射定义只剩 src/shared/artifact-labels.ts 一处；②pnpm vitest run tests/artifact-labels.test.ts tests/stage-panel.test.ts 全绿；③pnpm typecheck && pnpm build 通过；④浏览器核对清单逐项打勾并在任务卡留痕（哪页看到什么）

## 实施方案（implementation）
1. 跑 test-cases.md T-2 全部四条验收命令留输出；旧表名全仓 grep 确认除 DOC_KIND_META 兼容导出外无残留。2. pnpm typecheck && pnpm build（含 WRAP_SENTINEL 哨兵）通过。3. 浏览器 :13080 打开本需求详情页，对照 prototype.html §1–§5 黄底差异逐项核对：追溯链全中文、无「任务卡×N」、无英文枚举、归档清单 requirement=「需求文档」、未知值兜底形态。4. 核对结论写 reqboard_task_report 留痕。

## 上游产出摘要（dependsSummary）
- 收敛文档区两处引用（artifacts / verification）
- 收敛 client 工具回执引用（toolviews 三文件）
- 收敛 host 工具回执引用（render-summaries）
- 追溯链标签改造（文件名中文 + 任务卡逐张展开）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T13:54:24.137Z，窗口 session-89aa3b25-9e19-48c0-a032-cf932135f88b）

兼容收尾核查完成（机器可核验项全绿）：①测试 70/70（artifact-labels 17 + stage-panel 53）；②grep 唯一性——「需求文档」中文映射定义只剩 src/shared/artifact-labels.ts 一个文件；③pnpm typecheck + pnpm build（含 WRAP_SENTINEL 哨兵）通过，浏览器实际加载的 lib/client.js 已核验含「架构文档」「任务卡 · 」「产物（」且「任务卡×」折叠逻辑已消失；④旧表名残留扫描干净（SUBMIT_KINDS 是工具参数枚举非中文表，DOC_KIND_META 为验收允许的兼容导出）。⑤全量回归 1669 条中 4 条红——逐条归因全部非本需求：3 条是共享工作区另一窗口未提交改动（board.ts 归档栏删除/capture 系 ID 格式/src/index.ts 超 400 行+diag-log.ts 层边界），1 条是 vitest workers 模式不支持 process.chdir（--pool=forks 下即恢复）；本需求顺带修正了两条钉住旧行为的断言（「任务卡×」顺序断言、归档区「需求说明」漂移断言）。⑥浏览器像素级核对（prototype.html §1–§5 逐项打勾）需人眼，已留验收单。

### 完成项

- T-2 ①vitest artifact-labels+stage-panel 70/70 绿
- T-2 ②grep 唯一性：「需求文档」定义仅 artifact-labels.ts 一处（2 行：kind 层 + 文件名层）
- T-2 ③pnpm typecheck exit 0；pnpm build 通过（tsdown host + client + wrap + verify-client-build 哨兵 OK）
- T-2 ④旧表名残留：ARTIFACT_KIND_LABELS/SUBMIT_KIND/ARCHIVE_DOC_KIND_LABELS/KIND_CN 全仓零命中（SUBMIT_KINDS 参数枚举与 DOC_KIND_META 兼容导出属白名单）
- 浏览器 bundle 核验：lib/client.js（:13080 实际加载物）含新中文标签、无「任务卡×」；node_modules/dsh-pmboard 为指向仓库源码的符号链接，刷新页面即生效
- 全量回归归因：1669 条 4 红均非本需求（3 条他窗口在途改动 + 1 条 workers 环境问题），已修 2 条钉旧行为断言

### 改动文件

- `packages/web/dsh-pmboard/tests/acceptance-criteria.test.ts`
- `packages/web/dsh-pmboard/tests/client-view.test.ts`

### 下一步

浏览器像素级核对（哪页看到什么）由人在验收单复核；随后需求进 accepting

---
