---
requirement_refs: [FR-3]
---

# 数据模型（REQ-example）

## 实体关系 <!-- serves: FR-3 -->

```
┌──────────────┐ 1        N ┌──────────────┐
│ requirements │ ────────── │  artifacts   │
│  (需求表)    │            │  (产物表)    │
└──────────────┘            └──────────────┘
   主键: id                     外键: req_id → requirements.id
                                唯一键: (req_id, path)
   
关系说明：一个需求可以有多个产物（requirement.md / frontend.md / backend.md 等 17 类文档）
```

## 表/实体 <!-- serves: FR-3 -->

| 编号 | 表/实体 | 用途（存什么+支撑什么业务） | 关键字段（PK/FK/UK） |
|---|---|---|---|
| T-1 | artifacts（产物登记表） | 记录需求文档的落盘产物（模板骨架/手写文档），支撑幂等性检查和产物清单展示 | id(PK), req_id(FK→requirements), (req_id,path)UK |

### T-1 字段明细

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| id | INT AUTO_INCREMENT | 是 | - | 主键 |
| req_id | VARCHAR(50) | 是 | - | 需求 ID，外键指向 requirements.id |
| kind | VARCHAR(50) | 是 | - | 产物类型，枚举：template_skeleton(模板骨架) / manual_doc(手写文档) / design(设计) / test_case(测试用例) / review(评审) |
| path | VARCHAR(500) | 是 | - | 文件路径（工作区相对路径），如 docs/requirements/REQ-xxx/requirement.md |
| template_key | VARCHAR(100) | 否 | NULL | 模板 key（kind=template_skeleton 时必填），如 requirement.feature |
| summary | TEXT | 否 | NULL | 一句话摘要（提交时填写） |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 创建时间（UTC） |
| updated_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP ON UPDATE | 更新时间（UTC） |
| revision | INT | 是 | 1 | 版本号（同一 path 重交时 +1） |
| metadata | JSON | 否 | NULL | 扩展元数据，schema: {char_count: number, sections: string[]} |

## 索引与约束 <!-- serves: FR-3 -->

| 索引/约束 | 字段 | 理由（支撑哪个查询 + 为什么这些列） |
|---|---|---|
| uk_artifacts_req_path | (req_id, path) UNIQUE | 唯一约束：一个需求的一个路径只能有一条记录（幂等性保证）。支撑查询：`SELECT id FROM artifacts WHERE req_id=? AND path=?`（落盘前检查是否已存在）。选择性：组合唯一，100% 区分度 |
| idx_artifacts_req_kind | (req_id, kind) | 支撑查询：`SELECT * FROM artifacts WHERE req_id=? AND kind=?`（按类型筛选产物清单）。选择性：kind 有 5 种枚举值，req_id + kind 组合选择性高（约 1:3） |
| idx_artifacts_created | (created_at DESC) | 支撑查询：`SELECT * FROM artifacts ORDER BY created_at DESC LIMIT 20`（最近产物列表）。注意：DESC 索引，匹配排序方向 |

## 版本兼容 <!-- serves: FR-3 -->

### 本次变更：artifacts 表新增 kind 字段

**旧数据处理**：
- 存量 artifacts 记录的 kind 字段为 NULL（因为设置了默认值 NULL）
- 迁移脚本：`UPDATE artifacts SET kind='template_skeleton' WHERE template_key IS NOT NULL`
  （根据 template_key 是否为空推断类型）
- 迁移时机：部署后立即执行，预计 5 秒（存量约 1000 行）

**旧调用方兼容**：
- 旧代码不传 kind 字段 → 后端兜底逻辑，kind 为空时根据 template_key 推断
  （template_key 非空 → kind='template_skeleton'）
- 过渡期：1 个月，之后移除兜底逻辑，强制前端传 kind

**回滚可行性**：
- 可以回滚（新增字段，旧代码忽略即可）
- 回滚后数据：kind 字段仍存在但不被使用，无副作用
- 数据回滚：不需要（kind 字段留着不影响旧逻辑）
