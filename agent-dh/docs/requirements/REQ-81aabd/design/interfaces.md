---
req_id: REQ-81aabd
title: 设计 · 接口契约：提交口、查询口与渲染契约
serves: FR-1, FR-2, FR-4
---

# 设计 · 接口契约（REQ-81aabd）

## 1. 提交口（写）：`reqboard_submit`（serves: FR-4）

- **kind 取值范围**由 `ALL_ARTIFACT_KINDS.join(', ')` 生成，新增 `design` 后入参可传
  `kind='design'`（工具描述与错误消息同源，不会漏改）。
- `kind=plan`（拆分计划提交）的校验**一行未改**：仍要求状态 ∈ {design, decomposing…}、
  仍走 `missingCategoryDocs()` 齐备检查、仍只登记 `{stage:'design', kind:'plan'}` 一件产物。
- `kind=design` **不参与**任何闸门：它只是"把已在目录里的设计文档登记为设计文档"。

## 2. 阶段名契约（serves: FR-1, FR-2, FR-7）

| 层 | 写法 | 取值 |
|----|------|------|
| 代码（键/枚举） | 英文小写 | `design` / `decomposing` / `implementing` |
| UI 文案 | 中文 | 设计 / 拆分 / 实施 |
| 代码注释 | 中文（英文） | 设计（design）/ 拆分（decomposing） |
| 文档 | 中英并列 | 设计 / `design` / Design |
| 产出物 | 中文 + 文件名 | 拆分计划 `plan.md`（旧称"实施计划"作废） |
| 台账持久化值 | 英文小写 | `design`（`schemaVersion=7`）；旧值 `planning` 由迁移归一，读路径不认 |

唯一事实源：`docs/architecture/workflow-stages.md`（节点定义）+ 包内
`docs/stage-naming-final.md`（改名对照与落地范围）。改名前先读这两份，避免再次出现
"代码一个名、看板另一个名"。

**键改名的兼容契约（serves: FR-7）**：`reqboard_move.to` / 台账 `status` / `statusHistory[].status` /
`artifacts[].stage` 的合法取值一律为 `design`；`planning` 不再是合法入参（入参校验读状态机枚举）。
别名表 `LEGACY_REQ_STATUS_ALIASES` 只在 `src/domain/legacy/LegacyStatus.ts` 内定义、只被
`scripts/migrate-ledger.ts` 消费——**运行时不回退旧值**，避免"写新读旧"两套语义长期并存。

## 3. 查询口（读）：阶段详情（serves: FR-4）

`QueryStageDetail` 的 `DesignStageAssembler.buildBody` 输出：

```jsonc
{
  "plan": { /* 原样保留 */ },
  "category": "feature",
  "designDocs": [
    { "name": "architecture.md", "path": "docs/requirements/REQ-xxx/design/architecture.md", "submitted": true },
    { "name": "data-model.md",   "path": "...", "submitted": false }
  ]
}
```

契约：
1. `designDocs` 顺序 = `CATEGORY_DELTAS` 里该分类的 `requiredDesignDocs` 声明顺序（**稳定**，前端不做排序）；
2. 只在 `category` 已知时输出；未知分类 / 未传分类 → 字段缺省；
3. `submitted` 只反映**台账登记态**（不含实时文件扫描），与产物列表同源，两者不会互相矛盾。

## 4. 渲染契约（serves: FR-4）

`renderDesignBody` 对每份设计文档输出一行：

```html
<div class="dsh-pm-sn-dim" data-design-doc="architecture.md" data-submitted="yes">✅ 已交 · design/architecture.md</div>
<div class="dsh-pm-sn-dim" data-design-doc="data-model.md"   data-submitted="no" >⬜ 未交 · design/data-model.md</div>
```

- `data-design-doc` = 文件名（模板声明名），`data-submitted` = `yes|no`——**给自动化测试用的稳定契约**，
  文案可改、属性不改；
- `ARTIFACT_KIND_LABELS` 增 `design: '设计文档'`（产物列表与追溯链共用一张标签表）；
- `body.designDocs === undefined` → 回退旧渲染；`length === 0` → 「设计文档：无（本类型跳过设计文档）」。

## 5. 通知/消息（serves: FR-5）

同步后的审计评论用 `fmt()` 单模板拼装（域层禁用字符串拼接，见 `src/domain/text/fmt.ts`）：

```
[产物自动发现] 扫描需求目录：补登 {n} 个过程产物、回填 {m} 个过期种类（落进 docs/requirements/{id}/ 即产物）：
…
```
`{n}`/`{m}` 分列**补登**数与**回填**数，让"规则升级导致的重分类"在审计里可见，
不至于把回填误读成"又交了新文件"。返回值语义：补登数 > 0 返回补登数，**纯回填返回 0 但仍写台账**
（返回 0 = 没有新增文件，不代表什么都没做）。
