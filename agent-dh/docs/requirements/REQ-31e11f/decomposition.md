# 拆分方案：会话进度流程节点可点击查看详情

计划：plan.md（已批准 2026-09-15）

## 任务 DAG

| 任务 | 标题 | 阶段 | 端侧 | 依赖 |
|---|---|---|---|---|
| t-fb59e6 | 定义节点契约与产物模型（domain 层） | implement | backend | — |
| t-b28c68 | 实现 host 节点详情接口（模板装配器+路由） | implement | backend | t-fb59e6 |
| t-f264f4 | 实现 reqboard_task_report 任务完成汇报工具 | implement | backend | t-fb59e6 |
| t-ea210a | 实现产物登记钩子+分类感知闸门+阶段通知简版 | implement | backend | t-fb59e6, t-f264f4 |
| t-ab11f4 | 实现阶段提示词钩子（插件内常量，不走 skill） | implement | backend | t-fb59e6 |
| t-93b0b1 | 实现 client 节点详情面板（含分类流程图） | ui | frontend | t-fb59e6 |
| t-b84dca | 看板同源化+产物 chips+五门确认入口+派生展示 | implement | fullstack | t-b28c68, t-ea210a, t-93b0b1 |
| t-e728f6 | 测试补齐与全量回归（含接力实测） | test | backend | t-ea210a, t-ab11f4, t-b84dca |
| t-64a0c2 | 构建部署实测与文档更新 | merge | fullstack | t-e728f6 |
