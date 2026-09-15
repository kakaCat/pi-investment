# pmboard 新增工具设计

## 问题分析

当前 pmboard 状态机设计**已经很好**：
- **Requirement 层**：粗粒度阶段管理（立项→实施→验收→归档）
- **Task 层**：细粒度执行管理（开发→联调→测试→Review）

**不需要修改状态机**，而是需要：
1. 暴露更好的**查询工具**让用户看到细节
2. 增强**文档自动生成**
3. 提供**项目全景视图**

---

## 新增工具

### 工具 1: reqboard_overview（项目全景）

```typescript
/**
 * 项目全景报告 - 回答"项目在做什么"
 * 
 * 返回：
 * - 进行中需求列表（含任务进度明细）
 * - 最近完成需求
 * - 待人确认的项（验收/归档）
 * - 系统健康度
 */
reqboard_overview({
  window?: 'current' | 'all'  // 当前窗口 or 全部
})

// 返回示例：
{
  inProgress: [
    {
      id: 'REQ-xxx',
      title: '用户登录功能',
      status: 'implementing',
      taskBreakdown: {
        total: 5,
        inProgress: 2,    // 开发中
        integrating: 1,   // 联调中
        testing: 1,       // 测试中
        done: 1
      },
      lastUpdate: '2026-09-15 10:30'
    }
  ],
  pendingHumanAction: [
    { reqId: 'REQ-yyy', action: 'accepting', reason: '等待验收' }
  ],
  recentCompleted: [...],
  systemHealth: {
    docCoverage: 85,       // 文档覆盖率
    overdueTasks: 2,       // 逾期任务
    blockedReqs: 1         // 阻塞需求
  }
}
```

### 工具 2: reqboard_generate_doc（文档生成）

```typescript
/**
 * 自动生成结构化文档
 * 
 * 根据阶段生成不同文档：
 * - brainstorming: requirement.md（需求文档）
 * - planning: design.md（技术设计）
 * - accepting: verification.md（验收文档）
 */
reqboard_generate_doc({
  requirement_id: 'REQ-xxx',
  doc_type: 'requirement' | 'design' | 'verification',
  auto_fill?: boolean  // 是否自动填充已知信息
})

// 生成的文档会写入 docs/requirements/REQ-xxx/
```

### 工具 3: reqboard_read_context（读取项目上下文）

```typescript
/**
 * 读取项目 wiki 和相关文档
 * 
 * 在需求分析阶段自动读取：
 * - 架构文档
 * - API 清单
 * - 代码规范
 * - 数据库 schema
 */
reqboard_read_context({
  requirement_id: 'REQ-xxx',
  context_type: 'architecture' | 'api' | 'coding-standards' | 'all'
})

// 返回摘要供 LLM 参考
```

### 工具 4: reqboard_task_detail（任务详情）

```typescript
/**
 * 查看需求下所有任务的详细状态
 * 
 * 展示每个任务当前在哪个细分阶段
 */
reqboard_task_detail({
  requirement_id: 'REQ-xxx'
})

// 返回示例：
{
  tasks: [
    {
      id: 't-001',
      title: '实现登录 API',
      status: 'integrating',     // 联调中
      assignee: 'w-abc123',
      phase: 'backend',
      lastUpdate: '...',
      blockers: []
    },
    {
      id: 't-002',
      title: '登录页面开发',
      status: 'testing',          // 测试中
      phase: 'frontend',
      ...
    }
  ]
}
```

---

## SystemPrompt 增强

### 当前问题
SystemPrompt 只在**立项时**注入捕获引导，其他阶段没有指引。

### 解决方案
为每个阶段注入动态指引：

```typescript
// 需求分析阶段（brainstorming）
【需求分析阶段】
当前需求：{req.title}

你的任务：
1. 调用 reqboard_read_context 读取项目背景
2. 与用户讨论需求细节
3. 调用 reqboard_generate_doc 生成需求文档
4. 等待用户确认后推进到 planning

// 技术设计阶段（planning）
【技术设计阶段】
生成设计文档：
- 列出要改动的 API（新增/修改）
- 列出数据库变更（表/字段/迁移）
- 列出前端改动（页面/组件）

调用 reqboard_generate_doc(type='design')

// 实施阶段（implementing）
【实施阶段】
当前任务进度：{done}/{total}

下一个任务：{next_task.title}
• 状态：{next_task.status}
• 类型：{next_task.phase}

提醒：
- 完成开发后推进到 integrating（联调）
- 联调通过后推进到 testing（测试）
- 测试通过后推进到 in_review（等待 review）

// 验收阶段（accepting）
【验收阶段】
准备验收文档：
1. 调用 reqboard_task_detail 查看所有任务状态
2. 调用 reqboard_generate_doc(type='verification')
3. 提交验收：reqboard_verify_submit

等待用户验收通过。
```

---

## 人机回路明确标注

在工具文档中明确标注：

```typescript
// reqboard_move 工具的 description 增强
"推进需求状态。人工闸门（需要人在看板点击）：
• accepting → done（验收通过）
• done → archived（归档）
• 任意 → canceled（取消）

Agent 可自行推进的：
• draft → brainstorming（开工）
• brainstorming → planning（方案确认）
• planning → decomposing（拆分）
• decomposing → implementing（开始实施）
• implementing → accepting（提交验收）
"
```

---

## 实施优先级

### P0（立即实施，1-2小时）
- ✅ reqboard_overview（项目全景）
- ✅ reqboard_task_detail（任务详情）

### P1（本周，3-4小时）
- ⏳ reqboard_generate_doc（文档生成）
- ⏳ reqboard_read_context（读取上下文）
- ⏳ SystemPrompt 阶段指引增强

### P2（下周，2-3小时）
- ⏳ 与 wiki 的深度集成
- ⏳ Git 变更自动分析
- ⏳ 归档时自动合并文档

---

**开始实施 P0？**
