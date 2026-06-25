# PI Investment 调度架构设计

## 问题分析

**当前混乱**:
- crontab 配置调用 shell 脚本
- shell 脚本调用 quantsys-v2 API
- agent-ts 也有调度能力（但没用上）
- quantsys-v2 也可以有调度能力

**问题**: 谁负责调度？

---

## 系统调度能力分析

### 1. agent-ts 的调度能力

**位置**: `agent-ts/src/infrastructure/tools/monitor/monitor-schedule-tool.ts`

**能力**:
- 可以定时触发 agent 执行任务
- agent 是"大脑"，有决策能力
- 可以通过 LLM 理解复杂场景

**适合**:
- 需要智能决策的任务
- 需要理解上下文的任务
- 交互式任务

---

### 2. quantsys-v2 的调度能力

**可以实现**:
- Python 的 APScheduler
- Celery + Redis
- 或者不实现，由外部触发

**适合**:
- 固定流程的任务
- 批处理任务
- 不需要智能决策的任务

---

### 3. crontab

**能力**:
- 系统级定时调度
- 最可靠、最简单
- 无依赖

**适合**:
- 触发入口
- 确保任务不漏执行

---

## 推荐架构

### 方案 A: agent-ts 负责调度（推荐）

```
agent-ts (调度+决策)
    ↓ 内置调度器
    ↓ 9:00 触发
agent-ts 执行早盘分析
    ↓ 使用工具
    ↓ opponent-behavior-tool
    ↓ game-alert-tool
    ↓ ...
quantsys-v2 (肢体，被动响应)
    ↓ 提供 API
    ↓ /api/game/market/opponent-behavior
    ↓ /api/alerts/check
```

**优势**:
- agent 是大脑，由它调度更合理
- 可以智能决策
- 统一管理

**实现**:
```typescript
// agent-ts 内置调度
import schedule from 'node-schedule'

// 早盘分析 - 每个工作日 9:00
schedule.scheduleJob('0 9 * * 1-5', async () => {
  console.log('开始早盘分析')
  
  // 使用工具
  const opponents = await opponentBehaviorTool.execute()
  const alerts = await gameAlertTool.execute()
  
  // 智能决策
  if (alerts.critical.length > 0) {
    // agent 可以根据情况决定如何处理
  }
})
```

---

### 方案 B: 两级调度

```
crontab (触发)
    ↓ 每天 9:00
agent-ts (接收触发，执行决策)
    ↓ 使用工具
quantsys-v2 (肢体，被动响应)
```

**实现**:
```bash
# crontab 调用 agent-ts 的触发端点
0 9 * * 1-5 curl -X POST http://localhost:3000/trigger/morning-analysis
```

```typescript
// agent-ts 提供触发接口
app.post('/trigger/morning-analysis', async (req, res) => {
  // 执行早盘分析
  const result = await morningAnalysisFlow()
  res.json(result)
})
```

---

### 方案 C: quantsys-v2 调度（不推荐）

```
quantsys-v2 内置调度
    ↓ APScheduler
    ↓ 9:00 触发
执行工作流
    ↓ 调用 Services
```

**问题**: 
- quantsys-v2 是"肢体"，不应该主动调度
- 缺少智能决策能力
- agent 闲置

---

## 正确的架构

### 核心原则

**agent-ts (大脑)** 负责:
- 调度决策（什么时候做什么）
- 执行决策（如何做）
- 学习进化

**quantsys-v2 (肢体)** 负责:
- 被动响应 agent 的请求
- 提供数据和计算能力
- 执行具体操作

**web-frontend (窗口)** 负责:
- 展示 agent 的状态和决策

---

## 推荐实现

### Step 1: agent-ts 内置调度器

```typescript
// agent-ts/src/scheduler/index.ts
import schedule from 'node-schedule'

export class AgentScheduler {
  start() {
    // 早盘分析 - 工作日 9:00
    schedule.scheduleJob('0 9 * * 1-5', () => {
      this.morningAnalysis()
    })
    
    // 实时监控 - 工作日 9:00-15:00 每5分钟
    schedule.scheduleJob('*/5 9-15 * * 1-5', () => {
      this.realtimeMonitor()
    })
    
    // 每日学习 - 每天 18:00
    schedule.scheduleJob('0 18 * * *', () => {
      this.dailyLearning()
    })
  }
  
  async morningAnalysis() {
    console.log('🌅 开始早盘分析')
    
    // 使用工具
    const opponents = await opponentBehaviorTool.execute({})
    const alerts = await gameAlertTool.execute({})
    
    // 智能决策
    // ...
  }
}
```

### Step 2: agent-ts 启动时启动调度器

```typescript
// agent-ts/src/index.ts
import { AgentScheduler } from './scheduler'

const scheduler = new AgentScheduler()
scheduler.start()

console.log('✅ Agent 调度器已启动')
```

### Step 3: 使用 pm2 确保 agent-ts 持续运行

```bash
pm2 start agent-ts/dist/index.js --name pi-agent
pm2 save
pm2 startup
```

---

## 对比

| 方案 | agent-ts 调度 | 两级调度 | v2 调度 |
|------|--------------|---------|---------|
| 符合架构 | ✅ | ⚠️ | ❌ |
| 智能决策 | ✅ | ✅ | ❌ |
| 简单性 | ✅ | ⚠️ | ✅ |
| 可靠性 | ⚠️ | ✅ | ⚠️ |
| 推荐度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |

---

## 最终推荐

**方案 A + pm2**: agent-ts 内置调度 + pm2 进程守护

**理由**:
1. 符合控制论架构（大脑调度）
2. agent 有智能决策能力
3. 简单、统一
4. pm2 确保可靠性

**实现**:
1. agent-ts 内置 node-schedule
2. pm2 守护 agent-ts 进程
3. quantsys-v2 只提供 API
4. 不需要 crontab

---

## 迁移步骤

1. **在 agent-ts 中实现调度器** (2小时)
2. **配置 pm2** (30分钟)
3. **删除 crontab 配置** (如果有)
4. **测试** (1小时)

---

## 注意事项

1. **pm2 vs crontab**:
   - pm2 管理 agent-ts 进程
   - agent-ts 内部使用 node-schedule
   - 不需要 crontab

2. **可靠性**:
   - pm2 确保 agent-ts 不会挂
   - node-schedule 确保定时任务执行
   - 可以在 agent-ts 中添加健康检查

3. **监控**:
   - pm2 monit 查看进程状态
   - agent-ts 日志查看执行情况
   - web-frontend 展示 agent 状态
