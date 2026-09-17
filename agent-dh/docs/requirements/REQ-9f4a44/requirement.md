# REQ-9f4a44 流水线简化：验收通过后自动归档（移除 done 节点）

> 状态：需求分析（待确认）· 类型：refactor · 绑定窗口：w-24ded829
> 上游设计：[REQ-31e11f requirement.md](../REQ-31e11f/requirement.md)（五道人工确认门）· 前序：[REQ-ff20ca](../REQ-ff20ca/requirement.md)（确认门工具化）

## 1. 背景

**用户原话**：「归档自动完成，不应该有完成这个节点」

现状流水线：`… → accepting（验收）→（人工验收门）→ done（完成）→（人工归档门 + 归档材料）→ archived`

两个问题：
1. **多一个冗余节点**：done 只是"验收通过"的落点，语义上与验收通过重复，却占据了流程图一格里。
2. **归档是一道人工门**：人验完还要再点一次归档（并等 agent 备材料），回流一次。

## 2. 目标（三个决策已逐项确认）

| # | 目标 | 确认来源 |
|---|---|---|
| G1 | **移除 done 节点**——状态机与流程图同步去掉 | 两问确认时选定「状态机也去掉 done」 |
| G2 | **验收通过 → 直接进 archived**（人工验收门保留，人仍决定"过/退回"） | Q2 选定「直接进 archived」 |
| G3 | **验收通过后回落 agent 补归档材料**：系统向绑定会话注入"请准备归档材料"提示，agent 调 `reqboard_archive_submit` 补齐 | Q1 选定「验收通过后回落到 agent 补材料再自动归档」 |

**"自动"的准确语义**：人验收通过后**无需任何人再点归档**——归档状态自动落地，材料由 agent 补齐（archived 下允许 `archive_submit`）；看板对"材料待补"的 archived 显示标记。

## 3. 范围与影响面

| 面 | 改动 |
|---|---|
| **状态机** | `REQ_TRANSITIONS`：新增/改 `accepting → archived`；移除 done 相关转移 |
| **人工门** | `HUMAN_ONLY_REQ_TRANSITIONS`：移除 `done>archived`；验收通过（accepting→*）仍人工 |
| **确认门映射** | `ARTIFACT_CONFIRM_GATES`：`done>archived` 移除；`accepting>done` → 改为 `accepting>archived: 'verification'` |
| **流程图** | `conversation-progress.ts` 的 `FLOW` 去掉 done 格 |
| **分类档案** | `CATEGORY_FLOW_PROFILES` 各分类 stages/confirmGates 同步调整 |
| **归档校验** | `reqboard_archive_submit` 保留（备料时仍按分类校验必填文档），但不再是"人工门"，而是 archived 下的收尾动作 |
| **提示注入** | 验收通过后向绑定会话注入"请准备归档材料"（复用 capture-hook/stage-prompts 注入点） |
| **历史数据** | 老台账里的 `done` 记录：读取兼容、看板归入归档泳道或标注，不报错 |
| **看板** | archived 且无 archive 产物 → 显示"归档材料待补" |

## 4. 验收标准（待方案节细化）

1. 验收通过后状态**直接进入 archived**，全程无人工归档动作。
2. 绑定会话收到"请准备归档材料"提示；agent 在 archived 下调 `reqboard_archive_submit` 可用且材料校验生效。
3. 流程图与状态机均**不再出现 done 节点**。
4. 历史 `done` 记录可正常读取与展示（不报错、不丢数据）。
5. 单测覆盖：新转移（accepting→archived）、验收门保留、`done` 兼容路径、流程图无 done。

---

（方案节待第 1–4 节确认后撰写）
