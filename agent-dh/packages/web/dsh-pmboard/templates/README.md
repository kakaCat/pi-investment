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
├── brainstorming/        需求分析
│   └── requirement.<类型>.md  D1 需求说明（PRD；六类型独立模板，分开注入）
├── design/               设计
│   ├── architecture.md       D2 架构（feature / refactor）
│   ├── data-model.md         D3 数据模型（feature）
│   ├── interfaces.md         D4 接口（feature）
│   ├── test-cases.md         D5 测试用例（feature）
│   ├── use-cases.md          D6 用户场景（feature）
│   ├── frontend.md           D7 前端（条件：sides 含 frontend）
│   ├── backend.md            D8 后端（条件：sides 含 backend）
│   └── migration.md          D9 迁移（refactor）
├── decomposing/          拆分
│   └── decomposition.md      D10 拆分计划（全类型）
├── implementing/         实施
│   ├── task-card.md          D11 任务卡（全类型，每任务一份 → tasks/<taskId>.md）
│   ├── review-report.md      D12 评审报告（→ reviews/，验收要求非空）
│   └── test-evidence.md      D13 测试证据（→ tests/，验收要求非空）
├── accepting/            验收
│   └── verification.md       D14 验收材料（除 spike 外全类型）
├── archived/             归档
│   ├── retro.md              D15 复盘（bug / refactor / spike 必填）
│   └── index.md              D17 归档索引行（追加进 requirements/INDEX.md）
└── common/               任意节点兜底
    └── notes.md              D16 过程产物（原型/笔记/临时决定）
```

（draft 立项节点无文档——只有台账记录，故无对应文件夹。）

## 各节点落盘时点

| 节点转移 | 自动落盘（幂等"不存在才写"） |
|---|---|
| draft > brainstorming（窗口接手） | brainstorming/requirement.md → requirement.md |
| brainstorming > design（确认放行后） | design/*.md 按 category+sides 裁剪落盘 |
| decomposing 落卡 | decomposition.md + 每任务 task-card.md → tasks/<id>.md（现状已自动，换用本模板） |
| *> accepting | accepting/verification.md → verification.md |
| 归档 | archived/retro.md（按需）+ index.md 追加一行 |

## requirement 模板：六类型独立文件，分开注入

`brainstorming/` 下每类型一份成品模板，**无投影、无块标记**——
生成/注入时按立项类型一行映射，各取各的：

| 立项类型 | 模板文件 | 类型专属节（门禁必填） | 条款前缀 |
|---|---|---|---|
| feature | requirement.feature.md | 改动位置（流程图）/ 改动对比 / 产品定义 / 用户与角色 / 功能点（清单表）/ 功能点明细 | FR-x |
| refactor | requirement.refactor.md | 改动位置（流程图）/ 改动对比 / 现状 / 目标结构 / 行为不变式 | RF-x |
| bug | requirement.bug.md | 改动位置（流程图）/ 改动对比 / 复现步骤 / 根因 / 回归 | BUG-x |
| spike | requirement.spike.md | 待答问题 / 数据与方法 / 结论 | SP-x |
| doc | requirement.doc.md | 目标读者 / 大纲 | DOC-x |
| chore | requirement.chore.md | 完成判据 | CH-x |

注入映射：`templates/brainstorming/requirement.<category>.md` → 需求目录 `requirement.md`。

**防漂移约定**：六份的通用区（front-matter / 状态头 / 背景与动机 / 目标 / 非目标 /
边界 / 验收标准 / 修订记录）必须逐字一致——后续 check 脚本机械比对通用区，
不一致即 exit 1（同 check-prompt-fragments 模式）。类型专属节各自独立演化。

**行为改动区**（改动位置（流程图）+ 改动对比）：只有 feature/refactor/bug 三份有，
spike/doc/chore 没有——按「是否改系统行为」分界，与专业 PRD 的 "When Needed" 原则一致。

## 占位符

`{{REQ_ID}}` `{{TITLE}}` `{{CATEGORY}}` `{{WINDOW}}` `{{DATE}}` `{{TASK_ID}}` `{{TASK_TITLE}}`

## 门禁咬合点（模板为什么这么写）

- **节标题精确匹配**：hasRootSection 按「标题行 = 节名（可带编号/括号注）」匹配，
  故所有必填节标题原文保留（如 `## 边界（不做什么）`），改名即不合规。
- **serves 标注**：设计文档每章标题行带 `serves: FR-x`（或表格 serves 列 /
  front-matter requirement_refs），缺标注 = 孤儿章节被拦。
- **任务卡三要素**：`## 在做什么` / `## 解决什么问题` / `## 得到什么结果`
  是契约（task_card_incomplete 门禁按标题定位），不是排版。
- **front-matter 只放文档级索引**：逐条状态禁入（FRONTMATTER_PER_ITEM_KEY 探测）。

## 工程化（待实施，照抄 prompt fragments 模式）

- md 源文件 → 构建期 inline-templates 生成 `generated/templates.ts`（字符串常量进 dist bundle）；
- 运行时零 fs 依赖、零 files 白名单问题；浏览器端预览走 host HTTP 接口下发；
- check 门禁：源改了没重跑生成器 → exit 1。
