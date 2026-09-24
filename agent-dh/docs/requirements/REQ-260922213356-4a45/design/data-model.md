---
requirement_refs: [FR-1, FR-5, FR-7, FR-8]
---

# 数据模型（REQ-260922213356-4a45）

> 读者：实现本需求的 agent/开发。**本需求不改表、不动台账 schema、不做数据迁移**——
> 本文之所以仍要交，是因为"地址映射"是一种**持久事实源**（代码常量），必须把它的结构、
> 约束、版本兼容写清楚，否则改名/新增模板时会静默漂移。
> 编号 T-x 供 test-cases「被测对象」引用。

## 实体关系 <!-- serves: FR-1, FR-5 -->

```
   ┌────────────────────────────┐  N         1  ┌──────────────────────┐
   │ NODE_TEMPLATES             │ ────────────── │ templates/ 模板文件   │
   │ （代码常量：节点×类型→条目）│   relPath 引用 │ （插件包内磁盘文件）  │
   └────────────────────────────┘                └──────────────────────┘
              │
              │  1:1 同源校验（守护单测，非运行时常量）
              ▼
   ┌────────────────────────────┐
   │ 门禁文档集（事实源）         │
   │ effectiveDesignDocs /       │
   │ STAGE_ARTIFACT_REQUIREMENTS │
   └────────────────────────────┘

   ┌────────────────────────────┐  N         1  ┌──────────────────────┐
   │ DocRef（运行时投影，不落盘）│ ────────────── │ requirement.artifacts │
   │ 上游必读地址                │  只读，不写    │ task.cardDoc          │
   └────────────────────────────┘                └──────────────────────┘
```

关系说明：
- `NODE_TEMPLATES` 的每个条目指向一个模板文件（n:1，同文件可被多个节点/类型引用）；
- `NODE_TEMPLATES` 的内容必须与门禁文档集逐项一致（1:1 校验关系，由单测断言）；
- `DocRef` 是**运行时只读投影**，来源是既有台账（`requirement.artifacts` / `task.cardDoc`），本需求不写入。

## 表/实体 <!-- serves: FR-1, FR-2, FR-5 -->

| 编号 | 表/实体 | 用途（存什么+支撑什么业务） | 关键字段（PK/FK/UK） |
|---|---|---|---|
| T-1 | TemplateRef（模板条目常量） | 记录「某节点某类型该产出哪份模板」，支撑注入段渲染与漏配检测 | `id`(PK，代码内唯一), `(stage,category,relPath)`(UK) |
| T-2 | DocRef（上游必读投影） | 记录「本次开工前该读哪些已登记产物」，支撑实施节点纪律句 | `(kind,path)`(UK，同一次投影内) |
| T-3 | NODE_TEMPLATES（映射表容器） | 节点×类型 → TemplateRef[] 的静态索引，唯一地址事实源 | `(stage,category)`(UK) |

> **零表变更**：以上三者都不是数据库表、不落盘、不新增台账字段。持久化侧（requirements / artifacts）
> 保持原状——本需求只**读**它，不写它。

### T-1 TemplateRef 字段明细 <!-- serves: FR-2, FR-7 -->

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `id` | string | 是 | - | 稳定键，如 `design/architecture`；全表唯一（单测判重） |
| `stage` | string | 是 | - | 节点键，与 `StagePromptKey` 逐字一致：brainstorming/design/decomposing/implementing/accepting/archived |
| `category` | string | 是 | - | 类型键（feature/bug/doc/refactor/spike/chore）或 `'*'`（该节点通用） |
| `relPath` | string | 是 | - | 相对 templateRoot 的文件名，如 `design/architecture.md`；**不含** `..`、不以 `/` 开头 |
| `title` | string | 是 | - | 人读名，进指针行（架构设计 / 接口设计 …） |
| `purpose` | string | 是 | - | 一句话用途，进指针行；长度 ≤ 40 字（指针段总长 < 2KB 的保障） |

### T-2 DocRef 字段明细 <!-- serves: FR-5 -->

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `kind` | string | 是 | - | 产物类型：requirement / design / plan / decomposition / task / verification |
| `path` | string | 是 | - | 工作区相对路径（台账 `artifacts[].path` 原值或 `task.cardDoc`） |
| `title` | string | 是 | - | 人读名；kind 映射中文名（找不到映射时回落 kind 原文） |

### T-3 NODE_TEMPLATES 键结构 <!-- serves: FR-1, FR-7 -->

| 键 | 值 | 约束 |
|---|---|---|
| `stage`（节点） | `Category \| '*'` → `TemplateRef[]` | 节点必须属于 `PROMPT_STAGES`（6 个可注入节点） |
| 该节点下 `'*'` | 该节点所有类型共享的模板（如 design 的 architecture/data-model/interfaces/test-cases/use-cases） | 与类型专属条目**取并集**（专属在前，通用随后，顺序稳定） |
| 该节点下具体类型 | 该类型专属模板（如 refactor 的 migration、sides=backend 的 backend） | 未列出的类型 = 空集（不臆造） |

## 索引与约束 <!-- serves: FR-1, FR-2, FR-7 -->

| 索引/约束 | 字段/范围 | 理由（支撑哪个查询 + 为什么） |
|---|---|---|
| `uk_template_ref_id` 唯一 | `id`（全表） | 支撑：`NODE_TEMPLATES.flat().filter(t => t.id === x)` 必须恒返回 1 条。重复 id 会让单测与留痕无法定位条目 |
| `uk_stage_category_relpath` 唯一 | `(stage, category, relPath)` | 支撑：`resolveNodeTemplates(stage, category)` 结果稳定去重。同一格重复配置会让地址段出现重复行（用户可见噪音） |
| `chk_relpath_relative` 存在性+形态 | `relPath` | 支撑：`existsSync(path.join(templateRoot, relPath))` 恒真；且拒绝 `..`、绝对路径、空串（防路径穿越，见 architecture §安全） |
| `fk_relpath_template_file` 引用完整性 | `relPath` → `templates/**` | 支撑：守护单测遍历断言；断链 = **红灯**（不是运行时空集兜底） |
| `chk_parity_with_gate` 同源 | 整个表 vs 门禁文档集 | 支撑：`effectiveDesignDocs(category, sides)` 的每一份都在表中有条目，且表里的 design 条目也都在门禁文档集内（双向一致） |
| `chk_no_unreferenced_template` 漏配 | `templates/**` − 表引用集 | 支撑：目录里出现未被任何条目引用的模板 → 单测报警（改了模板名忘了改表 = 死链的反向形态） |

> 以上约束**全部由 `tests/template-address.test.ts` 机械断言**，不是文档口号；
> 数据库层无任何索引变更（零表变更）。

## 版本兼容 <!-- serves: FR-1, FR-8 -->

### 本次变更：无表结构/无持久化数据形状变更 <!-- serves: FR-1, FR-8 -->

**旧数据处理**：
- 不需要迁移、不需要回填、不需要双写；存量 `docs/requirements/**` 与 `dsh-reqboard.json` 原样可用。
- 存量需求（老记录、`artifacts` 为空的 legacy）→ 上游清单为空 → 地址段可能只有模板块（合法态）。

**旧调用方兼容**：
- `resolveStagePrompt` 的签名与返回**不变**；地址段在调用方通过 `augmentResolvedPrompt` 叠加。
- `ResolvedPrompt.charCount` 语义扩为「含地址段的注入文本长度」——这是**增强**不是破坏：旧读取方按字符数使用，数值变大但语义一致。
- 配置缺省：`addressSectionEnabled` 默认 `true`；未给 `templateRoot` 时走组合根按包根解析，仍为绝对路径。

**回滚可行性**：
- **可以回滚**：`git revert` 该提交即可；无数据面残留（地址映射是代码常量，删掉即消失）。
- **运行时常量回退**：`addressSectionEnabled=false`（配置）→ 立即回到改造前注入行为，不必重部署代码。
- **回滚后状态**：注入文本回到"只有阶段纪律"；守护单测随之删除；台账/文档零影响。

**不兼容变更示例（本需求不涉及，供参考）**：
- 若把 `relPath` 由"相对模板根"改为"相对仓库根"：所有存量地址失效、read 打不开（RISK-1 实测形态）
  → 必须同步改 `templateRoot` 语义 + 全量更新断言，且需要一次地址段重建。
