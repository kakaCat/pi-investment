# 模板包（dsh-pmboard 内置默认模板）

> 审核用。本目录是**插件内置的唯一模板事实源**：与门禁规则（category-doc-sets.ts /
> ArtifactSpec.ts / DocCompleteness.ts）同源设计，落笔即合规。
> 落盘时点 = 节点进入钩子（幂等"不存在才写"，永不覆盖已写内容）；
> 注入 LLM 的只有「指针 + 必填节清单」，模板全文不进提示词（token 预算）。

## 目录组织：按节点分文件夹（文件夹名 = 代码 StageKey）

生成器映射规则就一行：`templates/<stage>/<doc>.md` → 需求目录 `docs/requirements/<REQ>/…`，
stage 与代码 StageKey 逐字一致，零翻译层。

```
templates/
├── brainstorming/        需求分析（**只有 feature 经过此节点**）
│   └── feature.md  D1 需求说明（feature）
├── design/               设计（feature / bug / refactor 经过）
│   ├── (bug/refactor/chore/doc/spike 无独立需求文档，直接进入设计)
│   ├── 
│   ├── architecture.md         D2 架构（feature / refactor；TL;DR/总览图/方案对比/错误处理/上线回滚）
│   ├── data-model.md           D3 数据模型（feature）
│   ├── interfaces.md           D4 接口（feature）
│   ├── test-cases.md           D5 测试用例（feature）
│   ├── use-cases.md            D6 用户场景（feature）
│   ├── frontend.md             D7 前端（条件：sides 含 frontend）
│   ├── backend.md              D8 后端（条件：sides 含 backend）
│   ├── migration.md            D9 迁移（refactor）
│   └── prototype.html          D7+ UI 原型骨架（sides 含 frontend 时落盘 → prototypes/<name>.html）
├── decomposing/          拆分（feature / bug / refactor 经过）
│   └── decomposition.md        D10 拆分计划（任务表 + 跨文档覆盖对照）
├── implementing/         实施（全类型经过）


│   ├── 
│   ├── task-card.md            D11 任务卡（每任务一份 → tasks/<taskId>.md）
│   ├── review.md        D12 评审报告（→ reviews/）
│   └── test-evidence.md        D13 测试证据（→ tests/）
├── accepting/            验收
│   └── verification.md         D14 验收材料（除 spike 外全类型）
├── archived/             归档
│   ├── retro.md                D15 复盘（bug / refactor / spike 必填）
│   └── index.md                D17 归档索引行（追加进 requirements/INDEX.md）
└── common/               任意节点兜底
    └── notes.md                D16 过程产物（原型/笔记/临时决定）
```

**组织原则：文件夹 = 文档被产出的节点**（不是目标子目录）。同一节点的模板按类型分文件
（requirement.<category>.md）；落盘目标见「各节点落盘时点」表。
（draft 立项节点无文档——只有台账记录，故无对应文件夹。）


## 文档适用性矩阵：什么情况需要，什么情况不需要

两级判定：**先看类型必经哪些节点**（行），**再看本次改动性质**（「不交条件」列）。
满足不交条件就整份不交，不要交空壳——门禁只查「该交的交没交」，不惩罚不交。

### 需求文档（六类型各一，按首个启用节点落盘）

| 类型 | 模板 | 节点 | 什么时候不交 |
|---|---|---|---|
| feature | brainstorming/feature.md | brainstorming | 类型不是 feature |
| bug | brainstorming/bug.md | design | 类型不是 bug |
| refactor | brainstorming/refactor.md | design | 类型不是 refactor |
| spike | implementing/requirement.spike.md | implementing | 类型不是 spike |
| doc | implementing/requirement.doc.md | implementing | 类型不是 doc |
| chore | implementing/requirement.chore.md | implementing | 类型不是 chore |

### 设计文档（design/，feature 与 refactor 经过设计节点）

| 文档 | 类型范围 | 必交条件 | 不交条件（满足即整份不交） |
|---|---|---|---|
| architecture.md | feature / refactor | 默认交 | 单文件小改：无新组件/新依赖/新接口且改动 <50 行（TL;DR 并进 requirement 改动位置节）；bug/spike/doc/chore 不交 |
| use-cases.md | feature | requirement 的 UC 卡装不下的多角色/多分支场景 | UC 卡已覆盖且无新场景；其他类型不交 |
| interfaces.md | feature | 新增或变更接口 | 纯内部实现/纯展示、无接口变更；其他类型不交 |
| data-model.md | feature | 动表结构或持久化数据形状 | 纯内存计算/纯展示；其他类型不交 |
| frontend.md | feature | sides 含 frontend（门禁条件必交） | sides 不含 frontend |
| backend.md | feature | sides 含 backend（门禁条件必交） | sides 不含 backend |
| prototype.html | feature | sides 含 frontend | 同上 |
| migration.md | refactor | 有存量数据或旧调用方 | 全新启用、无存量；feature 的迁移考量写进 architecture.md 上线与回滚节 |
| test-cases.md | feature | 有可执行行为变化 | 只改文档/文案/注释；其他类型不交 |

### 拆分与实施文档（decomposing/ + implementing/）

| 文档 | 类型范围 | 必交条件 | 不交条件 |
|---|---|---|---|
| decomposition.md | feature / bug / refactor | 进入拆分节点必交（拆分门）；覆盖对照不齐不许批准 | spike/doc/chore 流程无拆分节点，不交 |
| task-card.md | 全类型 | 每落一张任务卡交一份 → tasks/<id>.md | 无任务不交 |
| review.md | 全类型 | 发生评审时（自评/交叉/验收评审）→ reviews/ | 无评审环节的小改不交 |
| test-evidence.md | feature / bug / refactor / chore | 有可执行行为变化（命令+输出证据）→ tests/ | doc/spike 纯文档/纯研究不交 |

### 验收与归档文档

| 文档 | 类型范围 | 必交条件 | 不交条件 |
|---|---|---|---|
| verification.md | 除 spike 外全类型 | 进验收节点必交 | spike 的结论节即验收产物，不交 |
| retro.md | bug / refactor / spike | 归档必填（教训复盘） | feature/doc/chore 可选（有教训就写） |
| index.md | 全类型 | 归档时追加一行进 requirements/INDEX.md | — |
| notes.md | 全类型任意节点 | 完全可选：过程产物/临时决定兜底 | 无 |

### 一句话原则

- **类型定节点，性质定文档**：类型决定你走哪条流水线（reqboard-category-flows.md），
  改动性质决定流水线里哪些文档这次可以不写。
- **「不交」也是合规状态**：交空壳占位反而污染归档；不交条件写进各模板首部，照章执行即可。
- **拿不准就交简版**：两可之间选「交但每节一行」，比整份不交更稳。
## 各节点落盘时点

需求文档的落盘节点**按类型的首个启用节点**定（依据 CATEGORY_FLOW_PROFILES，
详见 docs/architecture/reqboard-category-flows.md）：

| 类型 | 首个启用节点 | 落盘 |
|---|---|---|
| feature | brainstorming | brainstorming/feature.md → requirement.md |
| bug / refactor | design（免需求分析） | design/requirement.<类型>.md → requirement.md |
| spike / doc / chore | implementing（研究/写作即实施） | implementing/requirement.<类型>.md → requirement.md |

其余文档按节点转移落盘（全部幂等"不存在才写"）：

| 节点转移 | 自动落盘 |
|---|---|
| 进入 design | design/ 下该类型的设计文档骨架（feature 5 份+条件份 / refactor 2 份；bug 无） |
| decomposing 落卡 | decomposition.md + 每任务 task-card.md → tasks/<id>.md |
| *> accepting | accepting/verification.md → verification.md |
| 归档 | archived/retro.md（按需）+ index.md 追加一行 |

## requirement 模板：六类型独立文件，分开注入

`brainstorming/` 下每类型一份成品模板，**无投影、无块标记**——
生成/注入时按立项类型一行映射，各取各的：

| 立项类型 | 模板文件 | 类型专属节（门禁必填） | 条款前缀 |
|---|---|---|---|
| feature | feature.md（brainstorming/）| 改动位置 / 改动对比 / 产品定义 / 用户与角色（用户分析表）/ **核心场景** / 业务流程(可选) / 功能点（清单表·含配图列）/ 功能点明细 / 数据指标(可选) / **非功能需求** / 风险评估 / 迭代计划 | FR-x |
| refactor | requirement.refactor.md（design/）| 改动位置/ 改动对比 / 现状 / 目标结构 / 行为不变式 | RF-x |
| bug | requirement.bug.md（design/）| 改动位置/ 改动对比 / 复现步骤 / 根因 / 回归 | BUG-x |
| spike | requirement.spike.md（implementing/）| 待答问题 / 数据与方法 / 结论 | SP-x |
| doc | requirement.doc.md（implementing/）| 目标读者 / 大纲 | DOC-x |
| chore | requirement.chore.md（implementing/）| 完成判据 | CH-x |

注入映射：`templates/<首个启用节点>/requirement.<category>.md` → 需求目录 `requirement.md`（节点映射见上表）。

**防漂移约定**：六份的通用区（front-matter / 状态头 / 背景与动机 / 目标 / 非目标 /
边界 / 验收标准 / 修订记录）必须逐字一致——后续 check 脚本机械比对通用区，
不一致即 exit 1（同 check-prompt-fragments 模式）。类型专属节各自独立演化。

**行为改动区**（改动位置+ 改动对比）：只有 feature/refactor/bug 三份有，
spike/doc/chore 没有——按「是否改系统行为」分界，与专业 PRD 的 "When Needed" 原则一致。

## 写作原则（所有文档通用）

1. **简洁明了**：每个需求点直接、明确，不给读者留歧义
2. **场景化**：功能描述结合具体用户场景（谁、什么时候、为了什么）
3. **可衡量**：目标与指标给具体数值（"留存率提高 10%"而非"提高留存率"）
4. **术语一致**：全文统一术语与编号口径；术语表 When Needed 并入背景节

## 占位符

`{{REQ_ID}}` `{{TITLE}}` `{{CATEGORY}}` `{{WINDOW}}` `{{DATE}}` `{{TASK_ID}}` `{{TASK_TITLE}}`

## 门禁咬合点（模板为什么这么写）

- **节标题精确匹配**：hasRootSection 按「标题行 = 节名（可带编号/括号注）」匹配，
  故所有必填节标题原文保留（如 `## 边界（不做什么）`），改名即不合规。
- **serves 标注**：设计文档每章标题行带 `serves: FR-x`（或表格 serves 列 /
  front-matter requirement_refs），缺标注 = 孤儿章节被拦。
- **覆盖对照编号**：核心七件 FR-x（requirement）/ I-x（interfaces）/ P-x、C-x（frontend）/ S-x（backend）/
  TC-x（test-cases）/ t-x（decomposition）；按需扩展三件 T-x（data-model 表/实体）/
  UC-x（use-cases 场景）/ M-x（migration 步骤）。拆分计划按编号把文档拉齐；
  任一格为 0 且无理由 = 回退设计或需求补文档，不许批准。
  用例侧同规：test-cases 用例表的「被测对象」列必须引用设计编号——
  用例从设计文档推导，没有设计落点的用例 = 测空气。
- **下游文档锚点**：链条不止于拆分——任务卡「范围」节带设计落点 + 覆盖用例（TC-x）；
  测试证据对照表按 TC-x 回填执行结果；验收材料引用覆盖对照终态；
  评审报告含「编号可追溯」维度（serves/被测对象/落点悬空 = 没写）。
- **任务卡三要素**：`## 在做什么` / `## 解决什么问题` / `## 得到什么结果`
  是契约（task_card_incomplete 门禁按标题定位），不是排版。
- **front-matter 只放文档级索引**：逐条状态禁入（FRONTMATTER_PER_ITEM_KEY 探测）。

## 工程化（待实施，照抄 prompt fragments 模式）

- md 源文件 → 构建期 inline-templates 生成 `generated/templates.ts`（字符串常量进 dist bundle）；
- 运行时零 fs 依赖、零 files 白名单问题；浏览器端预览走 host HTTP 接口下发；
- check 门禁：源改了没重跑生成器 → exit 1。
