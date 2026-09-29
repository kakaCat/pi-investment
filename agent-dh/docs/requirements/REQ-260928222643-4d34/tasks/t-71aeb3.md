# t-71aeb3 styles/node-panel.ts 新增入口按钮与失败提示两条规则

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
styles/node-panel.ts 新增入口按钮与失败提示两条规则

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：ui
- 端侧：frontend

## 得到什么结果
cd packages/web/dsh-pmboard && npx vitest run tests/node-panel-styles.test.ts 全绿（TC-14 + 既有作用域断言）；grep -n "dsh-pm-np-board-entry|dsh-pm-np-entry-err" src/client/styles/node-panel.ts 两条规则均命中。

## 实施方案（implementation）
新增 .dsh-pm-np-board-entry（flex:none、min-height、胶囊、hover）与 .dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err 两条作用域内规则；不动 head-time 的 margin-left:auto；tests/node-panel-styles.test.ts 加 TC-14。

## 上游产出摘要（dependsSummary）
- node-panel.ts 加入口按钮并删除执行流程块调用与入参
- conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-28T14:59:54.008Z，窗口 session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd）

这一步做完，入口按钮在窄面板不被裁切、可点，失败提示在面板内红字可见，且没有新增任何裸全局选择器。

### 完成项

- 新增 .dsh-pm-np-board-entry（flex:none + min-height + hover）与 .dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err 两条作用域内规则
- tests/node-panel-styles.test.ts 新增 TC-14（15 条全绿，含既有作用域断言）

### 改动文件

- `packages/web/dsh-pmboard/src/client/styles/node-panel.ts`
- `packages/web/dsh-pmboard/tests/node-panel-styles.test.ts`

### 下一步

t8 构建发版

---
