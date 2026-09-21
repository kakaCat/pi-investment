---
requirement: REQ-84bea5
title: 数据模型设计
created: 2026-09-21
requirement_refs: [FR-2]
---

# 修复「批准计划→自动开跑」断链 - 数据模型

> serves: FR-2

## 1. 数据契约变更（serves: FR-2）

### 1.1 RequirementRecord 扩展（serves: FR-2）

**文件**：`src/domain/requirement/RequirementRecord.ts`

**变更类型**：字段新增

**变更内容**：
```typescript
interface RequirementRecord {
  // ... 既有字段
  
  advance?: {
    autoRun?: boolean;           // 既有：是否自动开跑
    pausedReason?: string;       // 新增：自动链失败原因
    // ... 其他既有字段
  };
}
```

**字段说明**：
- `pausedReason?: string`：自动链失败原因
  - **语义**：记录自动拆分/开跑失败的错误信息
  - **用途**：与手动模式区分（手动模式：无 `autoRun` 且无 `pausedReason`；自动链失败：有 `pausedReason` 且无 `autoRun`）
  - **值域**：错误消息字符串（如 "requirement_uncovered: FR-1, FR-2"）
  - **可选**：是（只在自动链失败时填充）

**向后兼容**：
- 既有需求的 `advance` 对象不受影响（可选字段）
- 手动模式需求不填充此字段
- 看板渲染时判断：`pausedReason` 存在 → 显示失败标记

## 2. 数据流（serves: FR-2）

### 2.1 写入路径（serves: FR-2）

```
AskConfirm.ts catch 路径
  ↓
await this.reqRepo.update(req.id, {
  advance: { 
    ...req.advance, 
    pausedReason: error.message 
  }
})
  ↓
RequirementRecord 持久化到 dsh-reqboard.json
```

### 2.2 读取路径（serves: FR-2）

```
看板前端加载需求列表
  ↓
req.advance?.pausedReason 存在 → 渲染失败徽标
  ↓
req.advance?.autoRun === true → 渲染自动链运行徽标
  ↓
两者皆无 → 渲染手动模式徽标
```

## 3. 数据示例（serves: FR-2）

### 3.1 自动链成功（serves: FR-2）

```json
{
  "id": "REQ-abc123",
  "status": "implementing",
  "advance": {
    "autoRun": true
  }
}
```

### 3.2 自动链失败（serves: FR-2）

```json
{
  "id": "REQ-abc123",
  "status": "decomposing",
  "advance": {
    "pausedReason": "requirement_uncovered: FR-1, FR-2 既没有被任何任务卡接收、也没有标「本轮不做」"
  }
}
```

### 3.3 手动模式（serves: FR-2）

```json
{
  "id": "REQ-abc123",
  "status": "implementing",
  "advance": {}
}
```

## 4. 数据完整性约束（serves: FR-2）

### 4.1 状态一致性（serves: FR-2）

- `autoRun === true` 时，`pausedReason` 必须为空（自动链成功运行）
- `pausedReason` 存在时，`autoRun` 必须为空或 false（自动链失败）
- 手动模式：两者皆为空

### 4.2 值域约束（serves: FR-2）

- `pausedReason`：非空字符串，长度 ≤ 2000 字符
- 格式：错误码 + 描述（如 "requirement_uncovered: ..."）

### 4.3 生命周期（serves: FR-2）

- **创建**：AskConfirm catch 路径写入
- **清除**：人工修复后调用 `reqboard_decompose` 成功时清除（或保留作历史记录）
- **持久化**：随 RequirementRecord 持久化到 `dsh-reqboard.json`

## 5. 迁移策略（serves: FR-2）

### 5.1 既有数据（serves: FR-2）

- 无需迁移：`pausedReason` 是可选字段
- 既有需求的 `advance` 对象保持不变
- 看板兼容：缺失字段时按手动模式渲染

### 5.2 回滚兼容（serves: FR-2）

- 回滚后：`pausedReason` 字段被忽略（不影响功能）
- TypeScript 编译：字段可选，不影响既有代码

## 6. 测试数据（serves: FR-4）

### 6.1 单元测试 Mock（serves: FR-4）

```typescript
const failedRequirement: RequirementRecord = {
  id: 'REQ-test',
  status: 'decomposing',
  advance: {
    pausedReason: 'requirement_uncovered: FR-1'
  }
};
```

### 6.2 集成测试种子（serves: FR-4）

```typescript
// 双源皆空，触发失败
const seedRequirement = {
  requirement_md: 'FR-1: 功能点一',
  decomposition_md: '| T1 | 任务一 | - |',  // 无覆盖
  plan: { tasks: [{ key: 'T1' }] }          // 无 requirement_refs
};
```

## 7. 关联数据模型（serves: FR-2）

本次变更不涉及以下模型：
- `TaskRecord`：不新增 `requirement_refs` 字段（绑定仍随 RTM 持久化）
- `PlanRecord`：不扩展 schema（plan 对象不是正源）
- `CommentRecord`：复用既有结构（系统评论）