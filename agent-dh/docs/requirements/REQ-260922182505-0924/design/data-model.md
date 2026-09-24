---
requirement_refs: BUG-1
---

# 数据模型 · REQ-260922182505-0924

## 零迁移 `serves: BUG-1`

台账 schema 不变：triages 数组保留，存量 2 条（均 resolved，最新 2026-09-08）原样加载。新流程不再写入（写端已随旧流程退役）。无回填、无字段删除、无版本号变更——这是"删行为留数据"取舍的落点。

## 客户端类型 `serves: BUG-1`

client/types.ts 的 TriageList/TriageRecord 是前端视图类型（非台账契约），随面板删除。shared/protocol.ts 的同名类型保留（台账契约）。
