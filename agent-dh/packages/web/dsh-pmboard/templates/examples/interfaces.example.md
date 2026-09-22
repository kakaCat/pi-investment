---
requirement_refs: [FR-2, FR-3, FR-5]
---

# 接口设计（REQ-example）

## 接口清单 <!-- serves: FR-2 -->

| 编号 | 接口 | 输入 | 输出 | 兼容性 | 错误语义 | serves |
|---|---|---|---|---|---|---|
| I-1 | getTemplate（模板常量模块导出，落盘钩子调用） | stage: StageKey, category: Category, doc?: string | 模板全文字符串 / null | 新增 | null=无模板，调用方降级跳过 | FR-2 |
| I-2 | listRequiredSections（门禁同源导出） | category: Category | string[]（必填节清单） | 新增 | 未知类型抛 ArgumentError | FR-5 |
| I-3 | onRequirementTransition（落盘钩子，挂 transitionRequirement 后置） | reqId, fromStage, toStage | void | 新增 | 内部全捕获，不抛给转移主流程 | FR-3 |

## 调用时序 <!-- serves: FR-3 -->

```
钩子                模板常量           文件系统
 │ getTemplate       │                 │
 │ ────────────────► │                 │
 │ ◄───────────────  │ md 字符串 / null │
 │ null → 告警+返回（不阻断）            │
 │ exists(target)?   │                 │
 │ ──────────────────────────────────► │
 │ ◄────────────────────────────────── │ true → 跳过（幂等）
 │ writeFile(骨架)    │                 │
 │ ──────────────────────────────────► │
 │ 抛错 → catch → 记 comments，不抛出    │
```

## 错误语义 <!-- serves: FR-3, FR-5 -->

| 错误码/情形 | 含义 | 调用方处置建议 |
|---|---|---|
| getTemplate 返回 null | 该节点无此类型模板 | 跳过落盘，属正常路径（如 draft 无模板） |
| listRequiredSections 抛 ArgumentError | category 非法 | 上游校验，不该发生；发生即 bug |
| submit 校验返回缺节清单 | 文档不合规 | 展示清单给 agent 补节后重交 |
