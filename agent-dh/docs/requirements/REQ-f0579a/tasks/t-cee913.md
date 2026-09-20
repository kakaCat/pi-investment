# t-cee913 尺寸拆分、杂项清理与全量终验

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
尺寸拆分、杂项清理与全量终验

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果
size-budget 转绿（index.ts、styles/base.ts ≤400 行）；npx vitest run 全量 0 失败；tsc --noEmit 绿；pnpm build 成功且 verify-client-build 通过

## 实施方案（implementation）
①index.ts 抽 gate 装配块到新文件（≤400 行）；②styles/base.ts 移一段 CSS 到合适 styles 子文件；③删 src/adapters/CaptureHook.ts.backup；④render/dom-utils.ts renderMarkdown 链接加协议白名单（http/https/mailto/相对路径）；⑤全量终验+git 提交

## 上游产出摘要（dependsSummary）
- 修 verdicts.ts 覆盖通过丢留痕
- 恢复看板视图三处回归
- 精确化操作条 move-req 断言
- 清偿架构门禁债

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T13:04:29.564Z，窗口 session-dd6cfa29-d8ff-43fe-99d7-371a69442076）

尺寸拆分、杂项清理与全量终验完成：index.ts 432→379 行（闸门后置链与捕获引导段两个装配块抽到 src/gate-wiring.ts，注释随代码搬）；styles/base.ts 408→397 行（需求卡高亮动画归入 board.ts，卡面样式归看板分片）；删除死文件 CaptureHook.ts.backup（实为未追踪残留）；renderMarkdown 链接加协议白名单（javascript:/data: 不再渲染为可点链接，配 3 条回归测试锁定）。终验：vitest 114 文件 1407 用例 0 失败（审计时 17 失败的五群全部转绿）、tsc 零错误、pnpm build + verify-client-build 哨兵通过。

### 完成项

- index.ts 抽 gate 装配块 + 捕获引导段到 gate-wiring.ts（379 行，门禁 ≤400）
- base.ts 高亮动画移入 board.ts（397/400 行，均达标）
- CaptureHook.ts.backup 删除（git 未追踪的死文件）
- renderMarkdown 协议白名单：先写红测试复现再修，tests/markdown-links.test.ts 3/3 绿
- 全量终验：1407/1407 通过 + tsc 绿 + 构建与 WRAP_SENTINEL 哨兵通过

### 改动文件

- `packages/pages/dsh-pmboard/src/index.ts`
- `packages/pages/dsh-pmboard/src/gate-wiring.ts`
- `packages/pages/dsh-pmboard/src/client/styles/base.ts`
- `packages/pages/dsh-pmboard/src/client/styles/board.ts`
- `packages/pages/dsh-pmboard/src/client/render/dom-utils.ts`
- `packages/pages/dsh-pmboard/tests/markdown-links.test.ts`
- `packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts.backup`

### 下一步

git 提交后推进任务状态；需求五个任务全部 done 后自动进入验收

---
