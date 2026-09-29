# t-bb1e62 跳转语义归位（selectPanel(null)）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
跳转语义归位（selectPanel(null)）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）；grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

## 实施方案（implementation）
改 packages/web/dsh-pmboard/src/client/session-jump.ts：删除 closeHostPanel() 与其 dsh-pmboard:open-board 派发；jumpToSession 改为先经 page-runtime 调 layout.selectPanel(null) 再 uiWorkspace.openSession(sid)；layout 不可用时返回 unavailable（不静默）；保留 archived/missing 判定与既有提示文案。

## 上游产出摘要（dependsSummary）
- 注册两端并接线（index.ts）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
