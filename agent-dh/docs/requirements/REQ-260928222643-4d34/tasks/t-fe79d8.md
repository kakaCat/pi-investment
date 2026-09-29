# t-fe79d8 board-mount.ts 挂载时 takeBoardFocus 初始化 mode·联调

> 任务卡骨架（自动链懒展开时只建了 TaskRecord、未落卡文档；本文件由窗口 `session-f17b3bd0` 按队列里的卡面事实回填，内容取自该子卡的实施方案与验收标准）

## 在做什么
board-mount.ts 挂载时 const focusReqId = takeBoardFocus()，据此把 mode 初始化为 {kind:'req',reqId} 否则 {kind:'board'}；陈旧 id 走既有 L240 回退，不动 render/fetchAll/SSE；扩展 tests/board-attach.test.ts 加 TC-7/TC-8 并补 serves 头。 [子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 解决什么问题
把父卡 **t-9b365a**（board-mount.ts 挂载时 takeBoardFocus 初始化 mode）的交付拆成「联调」阶段并独立验收，避免父卡一步到位、问题不可定位。

## 范围
- 阶段：implement
- 端侧：frontend
- 子卡阶段：integrate

## 得到什么结果

在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed、exit 0）；并核对 src/client/board-mount.ts 挂载闭包内 takeBoardFocus() 的调用与 src/client/board-focus.ts 的导出签名一致。

## 实施方案（implementation）
board-mount.ts 挂载时 const focusReqId = takeBoardFocus()，据此把 mode 初始化为 {kind:'req',reqId} 否则 {kind:'board'}；陈旧 id 走既有 L240 回退，不动 render/fetchAll/SSE；扩展 tests/board-attach.test.ts 加 TC-7/TC-8 并补 serves 头。 [子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 上游产出摘要（dependsSummary）
- t-1725e5

## 执行留痕（自动链 run）
- 状态：done｜尝试次数：0
- 产出（completed）：
- 接口联调通过（pass）：以真实 TS 模块（非单测桩）+ 真实台账接口 :13080 跑了一次端到端调用，请求样例与实际返回逐条与预期一致，allPass=true。 被测接口 = 设计 I-5「看板挂载点消费契约」：boardFocus.takeBoardFocus()（取走即清）→ mode 初始化为 {kind:'req',reqId} 否则 {kind:'board'}；消费端 board-mount.ts:184，登记端 board-focus.ts:21（经 board-entry.ts:70 / conversation-progress.ts:260 接线）。 四条请求样例：①登记真实在册 id REQ-260928222643-4d34 → 挂载渲染出 data-detail-req="REQ-260928222643-4d34"（htmlLength 71821），peekBoardFocus()/第二次 takeBoardFocus() 均为 undefined（恰好消费一次）；②无意图 → 默认看板（无 data-detail-req，htmlLength 5…
- 落盘改动（filesChanged）：
- （无落盘改动）

## 执行方式提示（executorHint）
本卡由自动链执行完成；卡面事实以 `../queue.json` 为准。不读会话历史，按本卡自足复核。
