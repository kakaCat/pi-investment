# t-d1a7f7 DAG 骨架皮肤换成 np 苹果风

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
DAG 骨架皮肤换成 np 苹果风

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：ui
- 端侧：frontend

## 得到什么结果

grep -n -- '--dsw-' packages/web/dsh-pmboard/src/client/styles/dag.ts 无输出； DAG_CSS 的 .dsh-pm-dag-panel 底色 = var(--dsh-pm-np-bg)（= 泳道图底色 #f5f5f7，2026-09-29 用户裁定，不得为白底）； cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts 全绿； cd packages/web/dsh-pmboard && pnpm build:client 退出 0 且输出含 [verify-client] OK

## 实施方案（implementation）
改 packages/web/dsh-pmboard/src/client/styles/dag.ts 的 DAG_CSS：面板用白底 + --dsh-pm-np-line-soft 描边 + 12px 圆角；标题用 --dsh-pm-np-text；-head 用 #f5f5f7（--dsh-pm-np-bg）底 + 下描边；-sub 与 -legend 用 --dsh-pm-np-text3 / -text2；-btn 与 -flowstat span 用 980px 胶囊，is-on 用 --dsh-pm-np-blue 实底；滚动条 8px 圆角。类名、styles.ts 的拼接与 scripts/verify-client-build.mjs 一律不动。

## 上游产出摘要（dependsSummary）
- 定契约：入参结构类型收敛 + 面板画布常量

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
