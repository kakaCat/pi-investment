# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

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
