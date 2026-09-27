---
id: rtm-infrastructure
title: RTM 追溯基础设施
summary: RTM 是什么、7 个文件与三级追溯链长什么样、代码在哪，以及"改了 src 不生效"和"工作区根被静默丢弃"两个必知运维坑。
type: architecture
status: living
updated: 2026-09-27
owners: [w-9f2c6c84]
tags: [rtm, traceability, reqboard, architecture]
related:
  - ../requirements/REQ-202609262349-1518/requirement.md
  - ../requirements/REQ-202609262349-1518/design/architecture.md
---

# RTM 追溯基础设施

## 它解决什么问题

需求流水线里"谁服务了哪条需求、哪个任务实现了哪段设计、哪条测试验证了哪个任务"，
原先只能**实时翻文档**猜（约 500ms/次，且口径不一）。RTM（Requirements Traceability
Matrix）把这套关系**预生成成 YAML 快照**，读取约 **2ms**——供看板「🔗 追溯」Tab 与
Dive 模式决策循环低成本读取。

**RTM 是台账的派生数据，不是事实来源。** 台账（`.dsh-data/dsh-reqboard.json`）才是；
RTM 随时可重新生成，删掉也不丢信息。

## 代码在哪

| 部分 | 位置 | 职责 |
|------|------|------|
| **生成器（canonical）** | `agent-dh/packages/tools/reqboard/src/rtm/` | 解析标注、构建追溯链、算覆盖度、读写 RTM 文件、门禁 |
| 触发点接线 | `packages/web/dsh-pmboard/src/application/internal/rtm-yaml.ts` | 把 7 个业务动作接到生成器 |
| 读盘装配 | `packages/web/dsh-pmboard/src/stage-overview/assembler.ts` | 把分节点的 RTM 文件合并成前端要的投影 |
| 前端渲染 | `packages/web/dsh-pmboard/src/client/views/traceability-view.ts` + `traceability-handler.ts` | 关系图 + 覆盖度卡片 + 双向高亮 |

## 7 个 RTM 文件

需求目录 `docs/requirements/<REQ>/` 下，每个节点一份：

| 文件 | 内容 |
|------|------|
| `rtm-lifecycle.yml` | 全流程里程碑/当前状态 |
| `rtm-brainstorming.yml` | 需求分析节点（提取的 FR 清单）|
| `rtm-design.yml` | `traceability.fr_to_design` + `coverage.design` |
| `rtm-decomposing.yml` | `traceability.design_to_tasks` / `fr_to_tasks` + `coverage.implementation` |
| `rtm-implementing.yml` | 任务列表 + 进度 |
| `rtm-implementing/<taskId>.yml` | 单任务详情（实施痕迹）|
| `rtm-accepting.yml` | `traceability.task_to_tests` / `fr_to_tests` + `coverage.testing` |

## 触发点（写路径）

| 业务动作 | 重新生成 |
|---------|---------|
| 立项 `reqboard_create` | lifecycle |
| `submit(kind=requirement)` | brainstorming + lifecycle |
| 确认产物 / 提交设计 | design + lifecycle |
| 批准拆分计划 | decomposing + implementing + lifecycle |
| 任务状态变更 / 任务汇报 | implementing（+ 单任务详情）|
| `submit(kind=verification)` | accepting + lifecycle |

**FR-9 铁律：RTM 是增强层，任何生成失败只记 warning，绝不打断主流程。**
读路径同理——RTM 缺失时前端降级为"无追溯数据"，详情照常渲染。

## 三级追溯链

```
FR-1 ──serves──▶ design/architecture.md#整体架构 ──implements──▶ t-354ea0 ──covers──▶ TC-1
（需求功能点）        （设计章节）                    （任务卡）              （测试用例）
```

另派生两个跨级映射：`fr_to_tasks`、`fr_to_tests`（由上面三级推导，不单独维护）。

## 覆盖度门禁

| 门 | 时机 | 阈值 |
|----|------|------|
| 设计覆盖度 | `submit(kind=design)` | **100%** |
| 实施覆盖度 | 批准拆分计划 | **100%** |
| 测试覆盖度 | `submit(kind=verification)` | **≥80%** |

不过门禁时**必须点名缺哪一项**（`uncovered` 清单），不能只报百分比。
边界语义：覆盖度 `total=0`（无项可判）时**不拦截**。

## ⚠️ 两个必须知道的运维坑（2026-09-27 实测）

### 1. 改了 `src/` 不一定生效 —— 必须构建

dsh-pmboard 的 `package.json` 是 **`main = ./dist/index.mjs`**、
**`exports["./client"] = ./lib/client.js"`**，服务加载的是**构建产物**。

> 仓库口径**不统一**：`bulletin/execution/holdings/reqboard` 等指向 `src/index.ts`（tsx 直载，免构建），
> 而 `dsh-pmboard/investment/intelligence/agent-dh-client` 指向 `dist/index.mjs`（**必须构建**）。

**改完必须跑完整流水线**（漏了后两步会"命令成功但产物没变"）：

```bash
cd agent-dh/packages/web/dsh-pmboard
pnpm build        # = tsdown(server) + tsdown(client) + wrap-client + verify-client-build
```

**判定是否生效看产物时间戳，不看退出码**：`ls -la dist/index.mjs lib/client.js`。

### 2. `deps.cwd` 全局未注入 —— 工作区根要靠兜底

pmboard 的 router deps 从未被注入 `cwd`，所以任何"读工作区文件"的功能都必须写成
`deps.cwd ?? process.cwd()`。写条件展开（`...(deps.cwd !== undefined ? {...} : {})`）会
**静默丢字段**——不报错、功能永远不出数据。追溯数据曾因此从不出现。

## 相关文档

- 需求与设计：`docs/requirements/REQ-202609262349-1518/`
- 使用指南：[`rtm-usage-guide.md`](../guides/rtm-usage-guide.md)
