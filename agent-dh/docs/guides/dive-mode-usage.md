# Dive 模式使用指南

**需求**: REQ-260925212722-96e7  
**更新**: 2026-09-25

## 什么是 Dive 模式？

Dive 模式是项目看板的自动流程控制机制，让需求能够自动完成从立项到归档的完整流程，减少人工干预。

## 快速开始

### 1. 创建需求

```typescript
// 创建需求时设置 dive.activation = 'armed'
const req = await reqboard_create({
  title: "实现新功能",
  category: "feature",
  summary: "功能描述...",
  // dive 会自动初始化为 armed
})
```

### 2. 自动推进

需求创建后，DiveManager 会自动：
1. 监听回合结束
2. 检查需求状态
3. 自动调用 agent 续跑
4. 推进到下一阶段

**不需要人工输入"继续"！**

### 3. 门禁检查

流程中会遇到三个门禁：

#### 设计门禁 (design → decomposing)
- **要求**: 所有功能点的 `design_refs` 已填写
- **示例**: `FR-1 design_refs: [architecture.md, api-design.md]`

#### 拆分门禁 (decomposing → implementing)
- **要求**: 所有功能点的 `task_refs` 已覆盖
- **示例**: `FR-1 task_refs: [t-abc123, t-def456]`

#### 验收门禁 (accepting → archived)
- **要求**: 所有功能点的 `acceptance_status = passed`
- **示例**: `FR-1 acceptance_status: passed`

### 4. 手动干预（当需要时）

如果需要手动操作，使用 `reqboard_clear_pause`：

```typescript
// 解除 armed 锁定
await reqboard_clear_pause({
  requirement_id: "REQ-xxxxxx"
})

// 现在可以手动操作
await reqboard_decompose({ ... })
await reqboard_move({ to: "implementing" })
await reqboard_task_move({ ... })
```

## 工作流程

### 完整流程图

```
立项 (draft)
    ↓ 手动推进
需求分析 (brainstorming)
    ↓ 写需求文档
设计 (design)
    ↓ 【设计门禁】检查 design_refs
拆分 (decomposing)
    ↓ 【拆分门禁】检查 task_refs
实施 (implementing)
    ↓ 完成任务
验收 (accepting)
    ↓ 【验收门禁】检查 acceptance_status
归档 (archived)
```

### 阶段说明

#### 需求分析 (brainstorming)
- **目标**: 理解需求，定义功能点
- **产出**: `requirement.md` (包含 FR 列表)
- **示例**: 
  ```markdown
  ## 功能需求
  
  - FR-1: 用户登录功能
  - FR-2: 密码重置功能
  ```

#### 设计 (design)
- **目标**: 设计架构、接口、数据模型
- **产出**: 设计文档 (在 `design/` 目录下)
- **门禁**: 每个 FR 必须有 `design_refs`

#### 拆分 (decomposing)
- **目标**: 把设计拆成可执行的任务
- **产出**: `decomposition.md` (拆分计划)
- **门禁**: 每个 FR 必须有 `task_refs`

#### 实施 (implementing)
- **目标**: 完成所有任务
- **自动**: 任务全部 done 后自动进入验收

#### 验收 (accepting)
- **目标**: 验证所有功能点
- **门禁**: 每个 FR 的 `acceptance_status` 必须是 `passed`

#### 归档 (archived)
- **目标**: 整理文档，合并到项目手册
- **产出**: 归档材料

## 常见问题

### Q: 如何停止自动续跑？

A: 有两种方式：
1. **达到回合数限制**: 系统自动暂停
2. **手动暂停**: 使用 `reqboard_clear_pause`

### Q: 门禁阻塞了怎么办？

A: 
1. 查看错误信息，了解哪些 FR 未通过
2. 补充缺失的内容（设计文档、任务、验收状态）
3. 重新推进

### Q: 可以手动推进吗？

A: 
- **armed 状态下**: 不可以，会被拒绝
- **解锁后**: 可以，使用 `reqboard_clear_pause` 解锁

### Q: 如何查看 dive 状态？

A: 使用 `reqboard_status`：

```typescript
const status = await reqboard_status()
// 查看 status.open_requirements[0].dive
```

### Q: 回合数限制是多少？

A: 根据阶段不同：
- brainstorming: 10 回合
- design: 10 回合
- decomposing: 5 回合
- implementing: 20 回合
- accepting: 10 回合

## 最佳实践

### 1. 清晰的功能点定义

在需求分析阶段，把功能点定义清楚：

```markdown
- FR-1: 用户登录功能
  - 支持用户名/密码登录
  - 支持第三方登录（微信、支付宝）
  - 登录失败后显示错误提示
```

### 2. 完整的设计文档

每个 FR 都应该有对应的设计文档：

```markdown
## FR-1: 用户登录功能

### 架构设计
- 前端：LoginPage 组件
- 后端：/api/auth/login 接口
- 数据库：users 表

### 接口设计
POST /api/auth/login
Request: { username, password }
Response: { token, user }
```

### 3. 任务覆盖所有功能点

拆分时确保每个 FR 都有任务覆盖：

```markdown
## 任务清单

- t-abc123: 实现登录 UI (FR-1)
- t-def456: 实现登录 API (FR-1)
- t-ghi789: 实现第三方登录 (FR-1)
```

### 4. 及时验收

完成任务后，及时更新 FR 的验收状态：

```markdown
- FR-1: 用户登录功能
  - acceptance_status: passed
  - acceptance_evidence: 测试通过，截图见 assets/
```

## 故障排查

### 问题: 自动续跑不工作

**原因**: 
- DiveManager 未初始化
- agents 服务不可用
- dive.activation 不是 'armed'

**解决**:
1. 检查 DiveManager 是否注册
2. 检查 agents 服务状态
3. 使用 `reqboard_status` 查看 dive 状态

### 问题: 门禁总是阻塞

**原因**: 
- FR 定义不完整
- design_refs / task_refs 未填写
- acceptance_status 未更新

**解决**:
1. 检查需求文档中的 FR 列表
2. 确保每个 FR 有对应的 design_refs / task_refs
3. 完成任务后更新 acceptance_status

### 问题: 手动操作被拒绝

**原因**: 
- dive.activation 是 'armed'

**解决**:
```typescript
// 先解锁
await reqboard_clear_pause({ requirement_id: "REQ-xxxxxx" })

// 再手动操作
await reqboard_decompose({ ... })
```

## 参考

- 架构文档: `docs/architecture/reqboard-dive-mode.md`
- 需求文档: `docs/requirements/REQ-260925212722-96e7/`
