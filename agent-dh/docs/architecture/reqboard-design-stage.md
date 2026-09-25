# 需求流水线 - 设计阶段规范

> 本文档记录设计阶段（design）的产物要求、闸门规则与内容约束。

## 设计文档集要求

### Feature 类型必需文档

根据 REQ-2d1c74 扩展，feature 需求的设计阶段必须交付以下文档：

1. **architecture.md** - 架构设计
2. **data-model.md** - 数据模型
3. **interfaces.md** - 接口设计
4. **test-cases.md** - 测试策略
5. **use-cases.md** - 用例文档（REQ-2d1c74 新增）

### 端侧条件文档

当需求涉及前端或后端改动时，需补充对应文档：

- **frontend.md** - 前端设计（涉及前端时必需）
- **backend.md** - 后端设计（涉及后端时必需）

声明方式：在需求文档的「边界」节说明，或通过 front-matter 字段标注。

### 小需求豁免

对于确实不需要完整文档集的小需求，可在 requirement.md 的 front-matter 添加：

```yaml
design_exempt: "豁免理由（如：纯文档修订，无用例）"
```

## G2 闸门规则

### 文档集完整性校验

**规则**：design → decomposing 转移前，代码级核验：
1. 该类型 requiredDesignDocs 全部存在
2. 全部 kind=design 产物均已确认

**实现**：`artifact-gates.ts` 的 `assertArtifactGates` 函数

**错误码**：`REQBOARD_DOC_INCOMPLETE`

未交齐时返回缺失清单，拒绝转移。

### 成组确认

设计文档采用**成组确认**机制：
- 确认任意一份 design/*.md 时，需逐份确认所有 design/*.md
- 或使用批量确认功能一次性确认全部

## 设计文档内容约束

### 拆分内容硬门禁（REQ-2d1c74 FR-3）

设计文档中**禁止**出现任务表或拆分内容。

**检测特征**：
- 任务表表头（depends_on、acceptance 列）
- 批次 DAG 图
- "拆分计划"章节标题
- 任务编号模式（t-xxx）

**实现**：`content-gates.ts` 的拆分内容检测

**错误码**：`design_contains_decomposition`

检出即拒绝确认，提示将该内容移至拆分阶段。

### 章节可追溯（语言强度按层）

每个设计章节应标注 `serves: FR-x` 说明服务哪个功能点。

参见：`design/heavy/overrides.md` 的语言强度按层指令。

## 登记入口与逐份登记态（REQ-260924213231-b1c4）

设计文档**不因落盘自动成为产物**：自动发现只发生在看板渲染路径。agent 侧的唯一登记入口是
`reqboard_submit(kind=design)`——缺省扫 `design/` 全目录、**幂等**（同 path 已登记不重计），
返回 `design_docs[]`（逐份 `on_disk` / `registered` / `confirmed`）与 `registered_count`。
`reqboard_status` 同样返回 `design_docs[]`：不打开看板也能读出「未登记 / 待确认 / 已落章」三态。

**不要猜 kind**：设计文档只认 `design`；`requirement` / `plan` / `verification` / `archive`
各对应别的阶段产物，传错会被工具枚举挡下（这就是旧版本里 agent 连撞三次枚举的根因）。

## G2 闸门拒绝信封（REQ-260924213231-b1c4）

同一道门原先把两种病因说成同一句「未确认」，agent 只能盲试到系统自己补登。现在按病因分化，
并各给**唯一可行下一步**：

| 病因 | 文案锚点 | 下一步 |
|---|---|---|
| 未登记（磁盘有、产物簿无此条） | 「未登记」 | `reqboard_submit(kind=design)` |
| 待确认（已登记但无确认章） | 「待确认」 | `reqboard_ask_confirm(target=artifact, kind=design)` |

所有内容闸门的拒绝消息统一为 `<工具> 未执行：<what> —— <why>。补齐：<how>`：`what` 是具体文件
或编号、`how` 是可复制的下一步；`code` 与 `gaps` 结构不变，**只改文案**（旧消费方读结构不受影响）。

## 历史演进

- **2026-09-25 REQ-260924213231-b1c4**：登记入口工具化（`reqboard_submit(kind=design)` + 逐份登记态投影）、G2 闸门按病因分化文案并统一拒绝信封、设计提示词写明登记命令与触发者（并明说「不要猜 kind」）
- **2026-09-21 REQ-2d1c74**：设计文档集扩展（use-cases + 端侧条件）、完整性前移到 G2、拆分内容硬门禁、产物可打开性校验
- **2026-09-17 前**：设计阶段允许包含拆分计划（已废弃）

## 相关文档

- [需求流水线工作流](../guides/reqboard-workflow.md)
- [文档集定义](../../packages/pages/dsh-pmboard/src/application/internal/category-doc-sets.ts)
- [产物闸门](../../packages/pages/dsh-pmboard/src/application/internal/artifact-gates.ts)
