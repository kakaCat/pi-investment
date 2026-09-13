# 需求归档规范（reqboard · agent-dh 执行细则）

> **上位规范**：文档放置规范 `docs/DOCUMENT-MANAGEMENT-PLAN.md`（项目级）。本文件是它在 reqboard
> 流程上的落地细则；**冲突时以项目规范为准**。代码级校验在
> `packages/pages/dsh-pmboard/src/shared/protocol.ts` 的 `ARCHIVE_DOC_RULES` +
> `assertArchiveMaterials` + `REQUIREMENT_DIR_PATTERN`——本文件与代码不一致时以代码为准，
> 改规则必须同时改这里。

## 0. 一条铁律：归档不许自创平行体系

项目已有文档规范目录——`docs/{adr,architecture,guides,rfcs,work-logs,strategy-research}`
（子项目对应 `agent-dh/docs/...`）。归档的**合并去向只能落在这些目录里**：
不允许因为"这次的东西不太一样"就新开一个 `known-issues/`、`research/`、`archive/`。

- 要新增一类目录 = **先改项目文档规范**（`DOCUMENT-MANAGEMENT-PLAN.md` + `docs/README.md`），
  再改代码里的 `ARCHIVE_DOC_RULES`，最后才用它归档；
- 代码会拒绝落在规范外的合并去向（`REQBOARD_INVALID_INPUT`）——这是代码闸门，不是提示词约定。

## 0.5 归档把认知推上金字塔（2026-09-13 追加）

归档不只是留证据，它让**项目认知自下而上生长**：

    L3 证据（需求档案 requirement/plan/verification/retro）
      → L2 领域篇（architecture / guides / adr / rfcs / strategy-research）
        → L1 说明书（docs/architecture/project-manual.md：项目是什么/架构/术语/去哪找）

- 每次归档：**L3 必写 + L2 至少一篇**（合并矩阵见 §3）；
- **改变了项目级认知**的类型（feature / refactor / spike）**必须申报说明书更新点**
  （`manual_updates`：path / section / summary）——代码会拒绝没有更新点的归档；
- 不改变认知的类型（bug / doc / chore）写 `manual_note` 说明即可；
- L1 每次变更要在说明书「最近更新」表追加一行（日期 / 更新点 / 来源 REQ）。

判据：**读完 L1 就该知道"这个项目是什么、现在有哪些关键认知"**；读不懂或找不到指针，说明这一层没维护。

## 1. 归档是什么：存底 + 合并

归档容易退化成两种失败：**挪目录式归档**（需求目录一挪，半年后没人知道结论）与
**到处撒文档**（文档全留在需求目录，项目文档永远停在两年前）。

因此归档是两条同时成立的动作：

| 动作 | 落在哪 | 回答什么 | 写作要求 |
|---|---|---|---|
| **存底**（档案） | `docs/requirements/REQ-xxxxxx/` | 当时为什么这么做 | 允许冗长、允许过程与失败尝试 |
| **合并**（知识） | 既有规范目录（按类型，见 §3） | 现在系统是什么样、有哪些坑 | 精炼、可检索、可被直接引用 |

一句话判据：**需求目录是档案，项目文档是活的知识**。同一句话不在两处各写一遍——
档案写过程与证据，项目文档写结论与用法，用 `REQ-xxxxxx` 互相引用。

## 2. 档案库结构

```
docs/requirements/REQ-xxxxxx/            # 项目根（跨项目/通用需求）
agent-dh/docs/requirements/REQ-xxxxxx/   # agent-dh 子项目（现网既有需求目录走这条）
  requirement.md    # 需求说明：背景 / 目标 / 边界（不做什么）/ 验收标准
  plan.md           # 实施计划（planning 阶段产出、人已批准的那份）
  verification.md   # 验收材料：做了什么、怎么验的、看到什么结果
  retro.md          # 复盘：踩了什么坑、哪些假设被证伪、下次怎么做
  notes.md          # 其他（可选）：运维细节、临时决定

requirements/INDEX.md   # 归档索引：REQ id | 一句话结论 | 类型 | 日期 | 目录 | 合并去向
requirements/_template/ # 模板：requirement / plan / verification / retro / troubleshooting-entry / research
```

- 目录名必须是 `REQ-<6 位 hex>`（`REQUIREMENT_DIR_PATTERN` 校验）；
- 档案**纳入版本控制**（与代码同仓），因为它是"为什么"的唯一证据链。

## 3. 合并矩阵：不同问题如何记录文档

按需求 `category` 决定**必填文档**与**合法合并去向**（代码校验，缺项/去错地方直接拒绝）：

| 类型 | 档案必填 | 合并去向（只允许规范目录） | 为什么要去那里 |
|---|---|---|---|
| `feature` | requirement, plan, verification | `architecture/`、`guides/` | 能力/接口变了，架构或使用指南必须同步 |
| `bug` | requirement, verification, **retro** | `guides/`（故障排查手册）、`architecture/`（机制性根因） | 规范没有单独的"已知问题"目录；根因写进排查手册或架构说明才会被读到 |
| `doc` | requirement, verification | `docs/` 对应子目录 | 产出本身就是文档 |
| `refactor` | requirement, plan, verification, **retro** | `adr/`（重大结构决策）、`architecture/`（过程可另记 `work-logs/`） | 结构与边界变了，必须有决策记录 |
| `spike` | requirement, **retro** | `rfcs/`（成提案）、`architecture/`（成认知）、`strategy-research/`（策略类） | 调研产物是结论；不留代码，但要留判断 |
| `chore` | requirement, verification | `work-logs/YYYY-MM/` | 留一条过程记录即可 |

**版本控制提醒**：`docs/work-logs/` 按规范**不纳入版本控制**。因此
**耐久结论（架构/决策/排查手册）绝不允许只落在 work-logs**——那里只放过程记录。

## 4. 三种合并方式

1. **追加小节**：在既有文档里加一节，正文末尾标 `（REQ-xxxxxx）`；
2. **新建文档**：主题自成一篇时——`adr/NNN-<title>.md`、`rfcs/NNN-<name>.md`、`architecture/<topic>.md`
   （命名遵循规范：ADR/RFC 数字编号，其余 kebab-case），并在归档索引登记；
3. **更新索引一行**：`requirements/INDEX.md`（本次归档）、`docs/README.md`（新文档入口）。

## 5. 流程与闸门

1. **窗口 agent 备材料**：`reqboard_archive_submit({ dir, docs[], merged_into[], index_entry })`
   —— 落库前按 §2/§3 逐条校验（目录形状、必填文档、合并去向、索引条目）；
2. **人点归档**：看板需求详情页「归档」（`POST /req/archive`，服务端再校验一次）→
   需求进 `archived`，写入 `archivePath` 与时间线事件。归档是人工闸门；
3. **合并动作由窗口真的做**：材料里写了 `architecture/x.md`，就得把那部分结论写进去；
   **只登记不合并 = 没归档**（下次审计会以"文档里没有对应内容"为由打回）。

## 6. 检索入口

- `agent-dh/docs/requirements/INDEX.md`：一行一个已归档需求（结论 + 去向）；
- `docs/README.md`：项目文档总索引（新文档必须挂上去，否则等于没写）。

## 7. 反模式（见过就改）

- 归档 = 把目录挪进 `archive/`，项目文档一个字没动；
- 自创目录（`known-issues/`、`research/`、`archive/`…）绕过规范；
- 把全文复制进项目文档（项目文档变垃圾场）——正确做法是提炼结论 + 链回档案；
- 复盘写成"加强重视"：复盘要求写清"哪些假设被证伪、下次怎么做"；
- 只登记 `merged_into` 而不改那些文件（材料与事实脱节）。
