---
requirement_refs: [FR-3]
---

# 数据模型（REQ-example）

（本需求不改表结构，只新增一种**产物登记形状**——骨架落盘后登记到需求 artifacts，
看板可见。）

## 实体关系 <!-- serves: FR-3 -->

```
┌─────────────┐ 1     n ┌──────────────────┐
│ requirement │ ─────── │ artifact（产物登记）│
└─────────────┘         └──────────────────┘
```

## 表/实体 <!-- serves: FR-3 -->

| 编号 | 表/实体 | 用途 | 关键字段 |
|---|---|---|---|
| T-1 | artifact 登记项 | 模板骨架落盘后的产物登记（复用既有 artifacts 结构，新增 kind 枚举值） | kind / path / stage / template_key |

### T-1 字段明细

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| kind | string | 是 | "template_skeleton" | 新增枚举值：模板骨架落盘产物 |
| path | string | 是 | — | 相对需求目录的落盘路径 |
| stage | string | 是 | — | 触发落盘的节点 |
| template_key | string | 是 | — | "<stage>/<doc>.md"，溯源用 |

## 索引与约束 <!-- serves: FR-3 -->

| 索引/约束 | 字段 | 理由（支撑哪个查询/防什么错） |
|---|---|---|
| 幂等约束 | (req_id, path) 唯一 | 防重复落盘重复登记——骨架是"不存在才写" |

## 版本兼容 <!-- serves: FR-3 -->

旧数据：存量需求无 template_skeleton 产物，读取侧按 kind 过滤不受影响。
旧调用方：artifacts 读取方对未知 kind 应跳过（既有行为，已确认）。
回滚：撤销本需求后已登记的产物保留（历史事实不回删），新需求不再产生。
