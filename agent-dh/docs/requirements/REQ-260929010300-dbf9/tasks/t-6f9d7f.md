# t-6f9d7f 画布 id 参数化 + 挂载实例表

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
画布 id 参数化 + 挂载实例表

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts 全绿，且新增用例断言：两个不同 canvasId 各挂载一次后释放其一，另一实例对应的画布元素仍存在于 DOM（两者互不释放）

## 实施方案（implementation）
改 packages/web/dsh-pmboard/src/client/views/dag-view.ts：①模块级单槽 activeDispose 换成 const disposers = new Map<string, () => void>()，disposeDagCanvas(canvasId) 只释放同名条目；②mountDagCanvas 用 document.getElementById(canvasId) 定位画布、openTaskDetail(taskId, canvasId) 定位锚点、挂载完成写入 disposers.set(canvasId, ...)；③改 packages/web/dsh-pmboard/src/client/dag-mount.ts：tryMountDagCanvas(tasks, ready?, canvasId='dag-canvas') 透传 canvasId。

## 上游产出摘要（dependsSummary）
- 定契约：入参结构类型收敛 + 面板画布常量

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
