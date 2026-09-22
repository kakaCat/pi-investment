# t-fb688e [FR-1~FR-5] 全量回归与实证验收（含兼容性验证）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
[FR-1~FR-5] 全量回归与实证验收（含兼容性验证）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果
全量测试 0 失败；验收判定 1-6 全部有证据（命令输出/日志/留痕文件）；plugin-schema.smoke 绿。

## 实施方案（implementation）
cd agent-dh && npx vitest run packages/web/dsh-pmboard；逐条核对 requirement.md「验收判定」1-6 并留证据；schema 冒烟 npx vitest run apps/web/tests/plugin-schema.smoke.test.ts。

## 上游产出摘要（dependsSummary）
- [FR-1] 更新 capture-tool.test.ts 为四问口径
- [FR-2] requirementDocPath 消费 docBasePath + 单测
- [FR-3] cordis.yml 开启 nodeIsolation 并重启验证
- [FR-4] state 端点暴露 workspaceRoot/homeDir + 客户端绝对路径打开与显示
- [FR-5] 立项拒绝粘滞：rejected 落痕 + 弹框前置检查 + 提示词纪律

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
