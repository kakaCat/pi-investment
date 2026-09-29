# t-470baa 定契约：入参结构类型收敛 + 面板画布常量·测试

> 需求：REQ-260929010300-dbf9 流程节点面板的 DAG 改用与需求详情一致的 Canvas 真图

## 在做什么
定契约：入参结构类型收敛 + 面板画布常量·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

## 汇报 1（2026-09-28T18:19:34.521Z，窗口 session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e）

父卡两条终态验收命令逐条执行：vitest 全绿（2 文件 / 74 用例，exit 0）；tsc 未通过（exit 2，208 条 error TS，67 个文件），目标命令未全绿 → 判 fail。tsc 报错与本卡改动零交集（无任何 dag-view.ts / DagTaskLike 相关错误），本卡契约本身（DagTaskLike 导出、PANEL_* 常量、三入口入参收敛且新参可选）在源码与单测中均就位且相应用例全绿；未改任何代码。

### 完成项

- 父卡两条终态验收命令逐条执行：vitest 全绿（2 文件 / 74 用例，exit 0）；tsc 未通过（exit 2，208 条 error TS，67 个文件），目标命令未全绿 → 判 fail。tsc 报错与本卡改动零交集（无任何 dag-view.ts / DagTaskLike 相关错误），本卡契约本身（DagTaskLike 导出、PANEL_* 常量、三入口入参收敛且新参可选）在源码与单测中均就位且相应用例全绿；未改任何代码。

---
## 汇报 2（2026-09-28T18:19:38.277Z，窗口 session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e）

父卡两条终态验收命令逐条执行：vitest 全绿（2 文件 / 74 用例，exit 0）；tsc 未通过（exit 2，208 条 error TS，67 个文件），目标命令未全绿 → 判 fail。tsc 报错与本卡改动零交集（无任何 dag-view.ts / DagTaskLike 相关错误），本卡契约本身（DagTaskLike 导出、PANEL_* 常量、三入口入参收敛且新参可选）在源码与单测中均就位且相应用例全绿；未改任何代码。

### 完成项

- 父卡两条终态验收命令逐条执行：vitest 全绿（2 文件 / 74 用例，exit 0）；tsc 未通过（exit 2，208 条 error TS，67 个文件），目标命令未全绿 → 判 fail。tsc 报错与本卡改动零交集（无任何 dag-view.ts / DagTaskLike 相关错误），本卡契约本身（DagTaskLike 导出、PANEL_* 常量、三入口入参收敛且新参可选）在源码与单测中均就位且相应用例全绿；未改任何代码。

---
