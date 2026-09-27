---
id: rtm-usage-guide
title: RTM 追溯使用指南
summary: 怎么写 serves/implements/covers 标注让追溯链长出来、在哪看、覆盖度怎么算，以及"追溯空白/DAG 无数据"的排查顺序。
type: guide
status: living
updated: 2026-09-27
owners: [w-9f2c6c84]
tags: [rtm, traceability, guide]
related:
  - ../architecture/rtm-infrastructure.md
---

# RTM 追溯使用指南

面向**写文档的人和看板的使用者**：怎么让追溯链长出来、怎么读覆盖度、看不到数据时怎么查。

## 一、三步让追溯链长出来

追溯关系**不靠手填台账**，而是靠文档里的**行内标注**（自动解析）。

### 第 1 步：设计文档章节标「服务哪些需求」

在 `design/*.md` 的章节标题处（同行或紧随其后一行）写：

```markdown
## 1.1 整体架构
<!-- serves: FR-1, FR-3 -->
```

→ 生成 `rtm-design.yml` 的 `fr_to_design`：`FR-1 → [design/architecture.md#整体架构, ...]`

### 第 2 步：任务卡标「实现哪段设计」

在任务卡（`tasks/<taskId>.md`）里写：

```markdown
<!-- implements: design/architecture.md#整体架构 -->
```

→ 生成 `rtm-decomposing.yml` 的 `design_to_tasks`

### 第 3 步：测试文档标「覆盖哪些任务」

在测试文档（`tests/*.md`）里写：

```markdown
<!-- covers: t-354ea0, t-354ea1 -->
```

→ 生成 `rtm-accepting.yml` 的 `task_to_tests`

**格式要点**：支持逗号分隔多值、支持中英文冒号（`:` / `：`）、忽略空白符、自动去重排序。

## 二、在哪看

| 入口 | 看什么 |
|------|--------|
| 看板 → 需求详情 → **「🔗 追溯」Tab** | 四列关系图（FR / 设计 / 任务 / 测试）+ 覆盖度卡片；**点任意节点会双向高亮关联节点** |
| `GET /dashboard/api/reqboard/requirements/<REQ>/stage/<stage>` | 响应 `body.traceability` 与 `body.coverage` |
| 需求目录的 `rtm-*.yml` | 原始快照（可 `grep` 快速查）|

## 三、覆盖度怎么算

| 覆盖度 | 分子 / 分母 | 门禁 |
|--------|------------|------|
| 设计 | 有设计章节服务的 FR / FR 总数 | 提设计时 **100%** |
| 实施 | 有任务实现的设计章节 / 设计章节总数 | 批准计划时 **100%** |
| 测试 | 有测试用例覆盖的任务 / 任务总数 | 提验收时 **≥80%** |

`rate` 是**百分比（0-100）**，不是 0-1 小数。未过门禁时错误信息里带 `uncovered` 缺口清单。

## 四、看不到数据？按这个顺序查

### 症状 A：追溯 Tab 空白 / 接口无 `traceability`

1. **该需求有没有 RTM 文件？**
   `ls docs/requirements/<REQ>/rtm-*.yml`
   没有 → 触发点没跑过（需求还没走到那些节点）。
2. **接口到底返回了什么？**
   `curl '/dashboard/api/reqboard/requirements/<REQ>/stage/design'`
   看 `body` 里有没有 `traceability` 键。
3. **代码改了但没生效？**（最常见）
   本项目 `main` 指向 `dist/`，**改 `src/` 必须跑 `pnpm build`**；
   且要核对**产物时间戳**（`ls -la dist/index.mjs lib/client.js`），别只看命令退出码。
4. **工作区根丢了？** 见 [架构文档的"运维坑"](../architecture/rtm-infrastructure.md)：
   必须写 `deps.cwd ?? process.cwd()`，写成条件展开会静默失效。

### 症状 B：**📊 DAG 层级没有数据**

DAG 渲染的是**台账里的任务记录**（`body.tasks`），**不是**计划里的卡。

- 若 `body.tasks = 0` 而 `body.planTasks = 14` → **计划已批准但任务卡从未落库**
  （`reqboard_decompose` 没执行）。此时 DAG / 泳道 / 实施覆盖度**都会是空的**——
  它们是同一个根因。
- 补救：批准过的计划可以落库（`reqboard_decompose`）。
- **注意**：若计划卡本身丢了依赖（`depends_on` 全为空），落库后 DAG 也只会是**平铺单层**，
  因为分层靠 `dependsOn` 算深度。要真正分层需重交计划补依赖并重新批准。

## 五、派生数据的确认提醒

RTM YAML 会以 `kind=notes` 被**自动发现登记**。它属于**派生数据**，不是五道人工确认门
（requirement / design / plan / decomposition / verification）。

若日志提示"notes 产物未确认"：它**不阻断任何流程**，可放心忽略或在看板点确认。
注意自动发现只增不减——删除文档后旧登记会残留，需要人工清理。

## 相关文档

- 原理与代码位置：[`rtm-infrastructure.md`](../architecture/rtm-infrastructure.md)
- 本需求档案：`docs/requirements/REQ-202609262349-1518/`
