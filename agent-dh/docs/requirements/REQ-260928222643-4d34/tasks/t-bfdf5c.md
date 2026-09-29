# t-bfdf5c 新增入口校验纯函数 src/client/board-entry.ts·联调

> 任务卡骨架（由窗口 `session-f17b3bd0` 按已批准计划补写——本环境的 auto-chain 执行器未产出 run 证据，故这三张父卡的子卡文档未自动生成；内容取自父卡 **t-dd5ba9** 的批准实施方案与验收标准）

## 在做什么
确认本卡产物与调用方/消费方的接线一致：新增入口校验纯函数 src/client/board-entry.ts

## 解决什么问题
本需求是浏览器侧单侧改动、无外部 HTTP 契约；联调=核对导入点、DOM 契约与类型面。

## 范围
- 阶段：implement
- 端侧：frontend
- 子卡阶段：integrate

## 得到什么结果

grep -n "activateBoardEntry" src/client/conversation-progress.ts 命中；在 packages/web/dsh-pmboard 下 pnpm run typecheck 对标改动文件无新增错误。

## 实施方案（implementation）
新建 board-entry.ts：activateBoardEntry(reqId,deps) 顺序 ①layout 可用性→②reqId 形状→③isKnown 台账可达性→④requestFocus；失败返回 {ok:false,reason,message} 且零副作用；文案对齐 interfaces.md I-2；新建 tests/board-entry.test.ts 覆盖 TC-9~13。
核对引用点与契约一致性（grep + pnpm run typecheck）；无新增网络契约。

## 上游产出摘要（dependsSummary）
- t-cb9237

## 执行方式提示（executorHint）
本卡所属父卡（t-dd5ba9）的实现已在本窗口完成并通过验证；证据见 reviews/review-report.md 与 tests/test-report.md。不读会话历史，按本卡自足执行。
