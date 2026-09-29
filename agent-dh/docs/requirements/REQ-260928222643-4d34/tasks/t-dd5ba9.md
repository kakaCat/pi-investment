# t-dd5ba9 新增入口校验纯函数 src/client/board-entry.ts

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
新增入口校验纯函数 src/client/board-entry.ts

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
cd packages/web/dsh-pmboard && npx vitest run tests/board-entry.test.ts 全绿（TC-9~TC-13）；三种失败路径 requestFocus 与 layout.selectPanel 调用各 0 次；成功路径 requestFocus 恰好 1 次。

## 实施方案（implementation）
新建 board-entry.ts：activateBoardEntry(reqId,deps) 顺序 ①layout 可用性→②reqId 形状→③isKnown 台账可达性→④requestFocus；失败返回 {ok:false,reason,message} 且零副作用；文案对齐 interfaces.md I-2；新建 tests/board-entry.test.ts 覆盖 TC-9~13。

## 上游产出摘要（dependsSummary）
- 新增一次性交接持有器 src/client/board-focus.ts

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-28T14:59:53.075Z，窗口 session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd）

这一步做完，入口有了一个可单测的「先校验、后切页」判据：activateBoardEntry 依次检查导航服务是否可用、REQ id 形状、台账是否可达，任一不过返回人话原因且零副作用。

### 完成项

- 新建 src/client/board-entry.ts（activateBoardEntry + boardEntryFailureMessage，纯函数+依赖注入）
- 新建 tests/board-entry.test.ts 覆盖 TC-9~TC-13（7 条断言全绿，含失败零副作用）

### 改动文件

- `packages/web/dsh-pmboard/src/client/board-entry.ts`
- `packages/web/dsh-pmboard/tests/board-entry.test.ts`

### 下一步

t3/t4 使用该校验结果决定是否切页

---
