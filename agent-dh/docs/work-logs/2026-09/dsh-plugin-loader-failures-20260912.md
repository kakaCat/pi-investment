---
id: wl-2026-09-dsh-plugin-loader-failures-20260912
title: DSH 插件加载失败（15 条 loader 事件）处置与发版闸门核验
type: worklog
status: archived
updated: 2026-09-12
owners: [w-32314d00]
tags: [worklog, 2026-09]
distilled_into: docs/standards/build-and-release.md
---

# DSH 插件加载失败（15 条 loader 事件）处置与发版闸门核验

- 时间：2026-09-13（本记录）／事件窗口 2026-09-12 15:54–15:57
- 窗口：w-32314d00（投资脑 investor）
- 事件指纹族：15 条 `Cannot find module '.../@pi-investment/quantsys-v2-client/dist/index.mjs'`

## 1. 现象

DSH :13080 实例在 2026-09-12 15:54–15:57 连续产生 15 条插件加载失败事件，
错误统一为无法解析顶层 client 包 `@pi-investment/quantsys-v2-client` 的 `dist/index.mjs`。
这 15 条在 Agent OS `public.error_events` 中处于 open/processing，未闭环。

## 2. 根因

不是插件代码缺陷，而是**构建窗口与运行实例的竞态**：

1. tsdown 构建为“先清空 dist、再写入产物”，构建期间该包 `dist/` 短暂不存在；
2. 实例若在此窗口重载插件（live 实例 + 仅构建不发版），模块解析即失败；
3. 该包当时确实存在“产物缺失”的瞬时状态 —— 现已恢复；
   现况：`quantsys-v2-client/dist/index.mjs` 59,530 字节，内置 19 包全部产物就绪。

关键区分：**这是瞬时窗口，不是持续故障**。发版脚本的完整路径（先 `launchctl bootout` 停服、
再构建、再校验、再 bootstrap）不会暴露在此窗口下；只有 `--build-only`（不停服）才会。

## 3. 处置

- 15 条事件逐条带证据闭环（含文件存在性、字节数、构建时间、实例健康度、无新增同类错误）；
- 终态台账：resolved 286 / ignored 103 / open 0 / processing 0（来源：`public.error_events` 聚合，2026-09-13）。

## 4. 预防（已落地）

`agent-dh/scripts/restart-with-build.sh` 的 `--build-only` 分支新增显式告警：
说明服务保持运行时 dist 会被短暂清空、以及该窗口会重现本轮 15 条 loader 失败，
并指引生产发版走完整路径。

同时核验既有闸门确实覆盖本族故障（此前未验证过，属“闸门在不在”的事实补全）：

```
$ ./scripts/restart-with-build.sh --check      # 退出码 0
---- dist 产物校验：19/19 通过
OK   quantsys-v2-client  ./dist/index.mjs  (59530 bytes)
状态统计: symlink-ok=25
OK: 已检查 25 个条目，均为指向仓库的符号链接（且非副本）。
```

即 `dist-packages.py verify` 与 `relink-profile.py --check` 已把两个顶层 client
（`quantsys-v2-client` / `agent-os-client`）纳入覆盖 —— 缺失/陈旧产物会在发版前被拒。

## 5. 残留风险与建议

- 残留：任何人在**运行中的实例**上手工跑构建（`--build-only` 或直接 `pnpm build`）仍会重现瞬时失败。
  仅靠脚本告警无法强制拦截；根治需构建期不破坏 `dist/`（先写临时目录再原子替换），属独立改造项。
- 依赖此类瞬时错误的另一类隐患：Agent OS 错误事件**不支持从 processing 回到 processing**，
  一旦事件被“认领”后处置动作失败，就只能靠人工闭环（本轮 18 条卡住事件即此因）。建议为
  processing 增加 stale-claim 超时回退。
