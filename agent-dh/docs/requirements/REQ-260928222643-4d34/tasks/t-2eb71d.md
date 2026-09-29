# t-2eb71d node-panel.ts 加入口按钮并删除执行流程块调用与入参

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
node-panel.ts 加入口按钮并删除执行流程块调用与入参

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
cd packages/web/dsh-pmboard && grep -n "renderProcessFold" src/client/node-panel.ts 无匹配；grep -n "injection|isolation" src/client/node-panel.ts 无匹配；npx vitest run tests/node-panel.test.ts 全绿且 7 节点输出不含「🔄 执行流程」；npx vitest run tests/node-panel-process-map.test.ts 仍全绿。

## 实施方案（implementation）
renderHead 内相对时间之后追加 button.dsh-pm-np-board-entry[data-action=np-board-entry][data-req]（文案固定 项目看板 ↗，跳过与正常分支共用）；删除 renderProcessFold 调用、ProcessFoldContext、NodePanelInput.injection/isolation 与相关 import 及头注；同步 tests/node-panel.test.ts（反写 TC-2、删 TC-4、加 TC-1/TC-2′/TC-5）。

## 上游产出摘要（dependsSummary）
- 新增一次性交接持有器 src/client/board-focus.ts
- 新增入口校验纯函数 src/client/board-entry.ts

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-28T14:59:53.339Z，窗口 session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd）

这一步做完，节点面板状态行出现「项目看板 ↗」且 7 个节点（含「本分类跳过」）全覆盖；面板里连「🔄 执行流程」那一行都不再出现，入参里的注入/隔离留痕一并删除。

### 完成项

- renderHead 追加入口按钮（data-action=np-board-entry / data-req / 固定文案）
- 删除 renderProcessFold 调用、ProcessFoldContext、injection/isolation 入参与相关 import
- tests/node-panel.test.ts 反写 TC-2、删除执行流程两组旧断言、新增 TC-1/TC-2′/TC-3/TC-5（26 条全绿）

### 改动文件

- `packages/web/dsh-pmboard/src/client/node-panel.ts`
- `packages/web/dsh-pmboard/tests/node-panel.test.ts`

### 下一步

t4/t6 接线与样式

---
