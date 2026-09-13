# 需求归档：文档合并规范

> 适用：项目看板（reqboard）需求完成后的归档。代码级规则在
> `packages/pages/dsh-pmboard/src/shared/protocol.ts` 的 `ARCHIVE_DOC_RULES` +
> `assertArchiveMaterials`——**本文件与代码不一致时以代码为准**，改规则须同时改这里和那里的 reason。

## 1. 为什么要"设计"归档

归档最容易退化成两种失败：

- **挪目录式归档**：需求目录一挪了事 → 半年后没人知道这次需求改了什么、结论是什么，文档等于不存在；
- **到处撒文档**：每份文档都留在需求目录里 → 项目文档（架构/指南/已知问题）永远停在两年前，新人只能读代码。

所以归档的定义是两条同时成立的**合并动作**：

1. **存底**：需求目录（`docs/requirements/REQ-xxxxxx/`）留全套原始材料——需求、计划、验收材料、复盘。
   它回答"当时为什么这么做"，允许冗长、允许过程性内容（对话结论、失败尝试）。
2. **合并**：把"别人以后要读的那部分结论"并进**项目文档**，并写一条索引条目。
   它回答"现在的系统是什么样、有哪些坑"，必须精炼、必须落在既定目录里。

一句话判据：**需求目录是档案，项目文档是活的知识**。同一句话不在这两个地方各写一遍——
档案里写过程与证据，项目文档里写结论与用法，用 REQ id 互相引用。

## 2. 目录约定

```
docs/requirements/REQ-xxxxxx/            # 项目根（跨项目/通用需求）
agent-dh/docs/requirements/REQ-xxxxxx/   # agent-dh 子项目（现网既有需求目录走这条）
  requirement.md    # 需求说明：背景 / 目标 / 边界（不做什么）/ 验收标准
  plan.md           # 实施计划（planning 阶段产出，人已批准的那份）
  verification.md   # 验收材料：做了什么、怎么验的、看到什么结果
  retro.md          # 复盘：踩了什么坑、哪些假设被证伪、下次怎么做
  notes.md          # 其他（可选）：运维细节、临时决定
```

校验（`REQUIREMENT_DIR_PATTERN`）：目录必须是上面的形状，且以 `REQ-<6 位 hex>` 结尾。

## 3. 合并矩阵（不同问题如何记录文档）

按需求 `category` 决定**必填文档**与**合法合并去向**——两者都由代码校验，缺项/去错地方会被拒绝：

| 类型 | 需求目录必填 | 合并去向（只允许这些前缀） | 理由 |
|---|---|---|---|
| `feature` | requirement, plan, verification | `agent-dh/docs/architecture/`、`agent-dh/docs/guides/`、`docs/architecture/`、`docs/guides/` | 能力/接口变了，架构或使用指南必须同步，否则新人只能读代码 |
| `bug` | requirement, verification, **retro** | `agent-dh/docs/known-issues/`、`docs/known-issues/` | 缺陷必须有根因与防回归，否则同类问题会再来一次 |
| `doc` | requirement, verification | `agent-dh/docs/`、`docs/` | 产出本身就是文档，直接进对应子目录 |
| `refactor` | requirement, plan, verification, **retro** | `agent-dh/docs/architecture/`、`agent-dh/docs/work-logs/`、`docs/architecture/`、`docs/work-logs/` | 结构与边界变了，架构说明必须同步，否则文档与代码互相说谎 |
| `spike` | requirement, **retro** | `agent-dh/docs/research/`、`docs/research/`、`docs/strategy-research/` | 产物是结论（含被证伪的假设），不进 research 就等于没做过 |
| `chore` | requirement, verification | `agent-dh/docs/work-logs/`、`docs/work-logs/` | 留一条工作记录即可，别把运维细节塞进架构文档 |

## 4. 三种合并方式

合并不是"再写一篇"，而是把结论**放进已有的阅读路径**：

1. **追加小节**（最常用）：在既有架构/指南文档里加一节，标题带需求语义，正文末尾标 `（REQ-xxxxxx）`；
   例：`docs/architecture/requirement-board.md` 加「## 状态时间线（REQ-b02e99）」。
2. **新建独立文档**：主题足以自成一篇时——已知问题 `known-issues/<slug>.md`、调研 `research/<topic>.md`；
   新建文档必须在归档索引里登记。
3. **更新索引/表格**：把结论变成一行——`known-issues/README.md` 的问题清单、`requirements/INDEX.md` 的归档条目。

**索引（`agent-dh/docs/requirements/INDEX.md`）**：每完成一次归档追加一行
`REQ id | 一句话结论 | 类型 | 日期 | 需求目录 | 合并去向`——它是"哪些需求做过、结论在哪"的唯一入口。

## 5. 归档流程（谁做什么）

1. **窗口 agent 准备材料**：`reqboard_archive_submit({ dir, docs[], merged_into[], index_entry })`
   —— 目录、文档清单、合并去向、一句话索引条目；代码按第 3 节的矩阵逐条校验。
2. **人点归档**：看板需求详情页「归档」按钮（`POST /req/archive`）→ 需求进入 `archived`，
   写入 `archivePath` 与时间线事件。归档是**人工闸门**（取消/归档/验收通过三处之一）。
3. **合并动作本身由窗口执行**（改那些项目文档），并把 `merged_into` 如实登记；
   归档材料里写了的去向，必须真的改到位（否则档案与项目文档再次脱节）。

## 6. 写文档的三条纪律

1. **结论先行**：项目文档里的每一节先给结论与用法，证据留给需求目录。
2. **一条问题一条记录**：`known-issues` 里的每个文件 = 一个问题（症状 / 影响 / 根因 / 修复 / 防回归），
   不合并多个问题，不写"若干问题汇总"。
3. **被证伪的假设也要写**：调研/复盘里明确写"我们原以为是 X，证据表明不是"——
   否则后来者会把同一个假设再试一遍（这是最贵的重复劳动）。

## 7. 反模式

- 归档 = 把目录挪到 `archive/` 却没有任何合并（项目文档不变 → 等于没归档）；
- 把全文复制进项目文档（项目文档变成垃圾场；正确做法是提炼结论 + 链回需求目录）;
- 用 `notes.md` 代替 `retro.md`（复盘要求"哪些假设被证伪、下次怎么做"，notes 不强制这些）；
- 合并去向写一个不存在的目录（校验会拦，别绕过）。
