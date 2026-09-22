# 拆分计划 · REQ-260922012924-2e29

目标：立项链路五处收口（FR-1~FR-5）按测试→纯函数→配置→全栈→留痕分卡实施，最后全量回归+实证验收。
做法：改动已在 design/interfaces.md 与 data-model.md 定死契约（requirementDocPath 拼接规则、BoardState 增字段、CaptureRejection 留痕结构），实施卡按契约落地；无迁移与兼容负担（台账零改动、老记录行为逐字节一致），兼容性并入回归卡验证。

## 任务表

| key | title | phase | side | depends_on | requirement_refs |
|-----|-------|-------|------|-----------|------------------|
| t1 | 更新 capture-tool.test.ts 为四问口径 | test | backend | — | FR-1 |
| t2 | requirementDocPath 消费 docBasePath + 单测 | implement | backend | — | FR-2 |
| t3 | cordis.yml 开启 nodeIsolation 并重启验证 | implement | backend | — | FR-3 |
| t4 | state 端点暴露 workspaceRoot/homeDir + 客户端绝对路径打开与显示 | implement | fullstack | — | FR-4 |
| t5 | 立项拒绝粘滞：rejected 落痕 + 弹框前置检查 + 提示词纪律 | implement | backend | — | FR-5 |
| t6 | 全量回归与实证验收（含兼容性验证） | test | fullstack | t1,t2,t3,t4,t5 | FR-1,FR-2,FR-3,FR-4,FR-5 |

说明：契约已在本目录 design/interfaces.md / data-model.md 定死（不再单设契约卡）；迁移与兼容无独立工作（零迁移），由 t6 统一验证；t3 涉及 launchd 重启（会话短暂中断，启动日志与 isolation-trace 为验收证据）。
