# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

## [Unreleased]

### Changed
- 页面名词统一（2026-09-21 用户裁定）：任务状态全套统一为长式
  待开始/开发中/联调中/测试中/**待复核**/已完成/已取消（`in_review` 此前在
  「验收 / 待评审 / 待复核」三名并存，且与需求级「验收」撞名）；Token tab 的
  legacy `done` 由「✅ 验收」改「✅ 完成」；toolviews 的 `plan` 产物标签对齐
  「拆分计划（旧版）」；执行 Tab 统计卡同步为 待开始/开发中；工具提示词与注释里
  节点 2 的禁用旧名「评审」统一为「需求分析」（workflow-stages.md 口径）
- 保留口径：会话底部徽标维持「实施中/待验收」；验收节点人工门措辞维持「审核」；
  评审阶段（task workflow review phase）节点内部状态维持「待评审/已批准/已退回」

## [0.1.0] - 2026-09-20

### Added
- 首个开源发布候选：DSH 需求流水线页面插件（项目看板）
- host 半：reqboard JSON + SSE API（/dashboard/api/reqboard/*）、JSON 台账两级状态机、
  立项捕获（capture hook + 三问弹框）、13 个 pm 工具（capture/create/status/move/
  decompose/submit/ask-confirm/accept-sheet/task-move/task-execute/task-status/task-report）
- client 半：GUI 侧栏入口 + 中心栏看板视图（泳道/时间线/验收单/归档区）

### Changed
- page-kit 工具库吸收为项目一等代码（client/dom、client/html、client/board-shell、client/render/pagination），插件不再依赖任何 workspace 协议包
- 服务端入口从 TS 源码改为编译产物 dist/index.mjs（tsdown 构建）
- 构建脚本去除 monorepo 相对路径，tsdown/tsx 声明为 devDependencies
