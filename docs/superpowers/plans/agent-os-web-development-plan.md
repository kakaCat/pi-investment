# Agent OS Web 监控面板开发计划

**版本**: v1.0  
**日期**: 2026-08-18  
**目标**: 6 周内完成 Agent OS Web 监控面板 (28 个页面)  
**执行方式**: 多 Agent 并行开发

---

## 一、项目结构

```
agent-os-web/                          ← 新建目录
├── public/
├── src/
│   ├── api/            # HTTP API 封装
│   ├── components/     # 通用组件
│   ├── views/          # 页面视图
│   ├── stores/         # Pinia 状态管理
│   ├── composables/    # 组合式函数
│   ├── router/         # 路由配置
│   ├── types/          # TypeScript 类型
│   ├── utils/          # 工具函数
│   ├── App.vue
│   └── main.ts
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── README.md
```

---

## 二、工作包划分 (Work Packages)

### 总体分工

| 工作包 | 负责人 | 工期 | 依赖 | 优先级 |
|--------|--------|------|------|--------|
| WP-1: 项目脚手架 + 基础组件 | Agent A | 3 天 | 无 | P0 |
| WP-2: 概览中心 (Overview) | Agent B | 4 天 | WP-1 | P0 |
| WP-3: 调度中心 (Scheduler) | Agent C | 5 天 | WP-1 | P0 |
| WP-4: 技能中心 (Skills) | Agent D | 4 天 | WP-1 | P0 |
| WP-5: 事件中心 (Events) + WebSocket | Agent E | 4 天 | WP-1 | P0 |
| WP-6: 决策中心 (Decisions) | Agent F | 3 天 | WP-1 | P1 |
| WP-7: 记忆中心 (Memory) | Agent G | 3 天 | WP-1 | P1 |
| WP-8: 通知中心 (Notifications) | Agent H | 3 天 | WP-1 | P1 |
| WP-9: 系统中心 (System) | Agent I | 3 天 | WP-1 | P2 |
| WP-10: 个人中心 (Profile) + 联调测试 | Agent J | 4 天 | WP-1~9 | P2 |

---

## 三、详细任务文档

---

### WP-1: 项目脚手架 + 基础组件

**负责人**: Agent A  
**工期**: 3 天  
**依赖**: 无  
**阻塞**: WP-2 ~ WP-10

#### 交付物

**Day 1: 项目初始化**

```bash
# 创建项目
mkdir agent-os-web && cd agent-os-web
npm create vue@latest . -- --typescript --router --pinia --vitest

# 安装依赖
npm install element-plus axios echarts monaco-editor vue-monaco
npm install -D @types/node sass
```

**文件**: `package.json`, `vite.config.ts`, `tsconfig.json`

**Day 2: 基础架构**

创建以下文件：

```
src/
├── api/
│   └── client.ts           # Axios 封装 + 统一错误处理
├── components/
│   └── layout/
│       ├── AppHeader.vue   # 顶部导航
│       ├── AppSidebar.vue  # 左侧菜单
│       ├── AppFooter.vue   # 底部
│       └── AppLayout.vue   # 整体布局框架
├── router/
│   └── index.ts            # 路由配置 (空路由，等 WP-2~10 填充)
├── stores/
│   └── app.ts              # 应用状态 (主题/语言/侧边栏折叠)
├── utils/
│   ├── request.ts          # Axios 实例
│   ├── format.ts           # 时间格式化、Cron 显示
│   └── constants.ts        # 常量
├── types/
│   └── index.ts            # 通用类型
├── App.vue
└── main.ts
```

**关键代码**: `src/utils/request.ts`

```typescript
import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080/api/v1',
  timeout: 30000,
})

// 统一错误处理
client.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.message || err.message
    // 全局 Toast 提示
    console.error('API Error:', msg)
    return Promise.reject(err)
  }
)

export default client
```

**关键代码**: `src/components/layout/AppLayout.vue`

```vue
<template>
  <el-container class="app-layout">
    <AppSidebar />
    <el-container>
      <AppHeader />
      <el-main>
        <router-view />
      </el-main>
      <AppFooter />
    </el-container>
  </el-container>
</template>
```

**Day 3: 通用组件**

创建以下组件：

| 组件 | 文件 | 说明 |
|------|------|------|
| StatusBadge | `components/common/StatusBadge.vue` | 状态标签 (成功/失败/警告/运行中) |
| TimeAgo | `components/common/TimeAgo.vue` | 相对时间显示 |
| CronDisplay | `components/common/CronDisplay.vue` | Cron 表达式转中文 |
| MetricCard | `components/common/MetricCard.vue` | 指标卡片 (数字+趋势) |
| ChartCard | `components/common/ChartCard.vue` | 图表卡片 (ECharts 封装) |
| DataTable | `components/common/DataTable.vue` | 数据表格 (排序/筛选/分页) |

**StatusBadge 组件示例**:

```vue
<template>
  <el-tag :type="typeMap[status]">
    {{ labelMap[status] }}
  </el-tag>
</template>

<script setup lang="ts">
const props = defineProps<{ status: string }>()

const typeMap: Record<string, string> = {
  success: 'success',
  failed: 'danger',
  running: 'primary',
  pending: 'info',
  timeout: 'warning',
}

const labelMap: Record<string, string> = {
  success: '成功',
  failed: '失败',
  running: '运行中',
  pending: '待执行',
  timeout: '超时',
}
</script>
```

#### 验收标准

- [ ] `npm run dev` 能正常启动，显示基础布局
- [ ] 左侧菜单显示 9 个一级分类 (空路由)
- [ ] Axios 能正确调用 `GET /health`
- [ ] StatusBadge 组件能正确显示 5 种状态
- [ ] 主题切换 (深色/浅色) 正常工作

---

### WP-2: 概览中心 (Overview)

**负责人**: Agent B  
**工期**: 4 天  
**依赖**: WP-1  
**阻塞**: 无

#### 交付物

**Day 1: API 封装 + 类型定义**

**文件**: `src/api/overview.ts`

```typescript
import client from './client'

export interface TaskStats {
  total: number
  running: number
  successToday: number
  failedToday: number
}

export interface SystemHealth {
  status: string
  services: Record<string, { status: string; latency: number }>
}

export function getTaskStats() {
  return client.get('/scheduler/tasks/stats')
}

export function getSystemHealth() {
  return client.get('/health')
}

export function getRecentExecutions(limit = 10) {
  return client.get('/scheduler/executions', { params: { limit } })
}
```

**文件**: `src/types/task.ts`

```typescript
export interface Task {
  id: string
  name: string
  owner: string
  cron: string
  enabled: boolean
  status: string
}

export interface TaskRun {
  id: string
  task_id: string
  task_name: string
  status: string
  started_at: string
  finished_at?: string
}
```

**Day 2-3: 系统总览页面**

**文件**: `src/views/overview/Dashboard.vue`

```
页面内容:
1. 4 个 MetricCard (总任务数/运行中/今日成功/今日失败)
2. 任务执行趋势图 (24h 折线图)
3. 系统健康状态列表
4. 最近执行任务 Top 10
5. 快捷操作按钮
```

**Day 4: 实时监控页面**

**文件**: `src/views/overview/Monitor.vue`

```
页面内容:
1. WebSocket 连接状态指示器
2. 实时事件流 (带过滤器的列表)
3. 实时任务执行状态 (运行中/排队中计数)
4. 系统资源使用 (CPU/MEM/DISK 进度条)
```

**WebSocket 封装**: `src/composables/useWebSocket.ts`

```typescript
export function useWebSocket(url: string) {
  const ws = new WebSocket(url)
  const events = ref<Event[]>([])
  const connected = ref(false)

  ws.onopen = () => { connected.value = true }
  ws.onmessage = (e) => {
    events.value.unshift(JSON.parse(e.data))
    if (events.value.length > 100) events.value.pop()
  }
  ws.onclose = () => { connected.value = false }

  return { events, connected }
}
```

#### 验收标准

- [ ] Dashboard 显示 4 个核心指标卡片
- [ ] 24h 执行趋势图能正常渲染 (ECharts)
- [ ] 系统健康状态显示 5 个服务状态
- [ ] Monitor 页面 WebSocket 连接成功，实时显示事件
- [ ] 事件过滤器能按类型筛选

---

### WP-3: 调度中心 (Scheduler)

**负责人**: Agent C  
**工期**: 5 天  
**依赖**: WP-1  
**阻塞**: 无

#### 交付物

**Day 1: API 封装**

**文件**: `src/api/scheduler.ts`

```typescript
import client from './client'
import type { Task, TaskRun } from '@/types/task'

export function listTasks(params?: { enabled_only?: boolean; owner?: string }) {
  return client.get('/scheduler/tasks', { params })
}

export function getTask(id: string) {
  return client.get(`/scheduler/tasks/${id}`)
}

export function createTask(data: Partial<Task>) {
  return client.post('/scheduler/tasks', data)
}

export function updateTask(id: string, data: Partial<Task>) {
  return client.put(`/scheduler/tasks/${id}`, data)
}

export function deleteTask(id: string) {
  return client.delete(`/scheduler/tasks/${id}`)
}

export function triggerTask(id: string) {
  return client.post(`/scheduler/tasks/${id}/trigger`)
}

export function pauseTask(id: string) {
  return client.post(`/scheduler/tasks/${id}/pause`)
}

export function resumeTask(id: string) {
  return client.post(`/scheduler/tasks/${id}/resume`)
}

export function listExecutions(params?: { task_id?: string; limit?: number }) {
  return client.get('/scheduler/executions', { params })
}

export function getTaskStats() {
  return client.get('/scheduler/tasks/stats')
}
```

**Day 2: 任务列表页面**

**文件**: `src/views/scheduler/TaskList.vue`

```
功能:
- 表格展示所有任务 (名称/调度/状态/所有者)
- 搜索框 (按名称搜索)
- 筛选器 (状态/所有者)
- 操作按钮: 触发/暂停/恢复/编辑/删除
- 批量操作
- 分页
- 新建任务弹窗 (表单: 名称/cron/webhook_url/owner/enabled)
```

**Day 3: 执行历史页面**

**文件**: `src/views/scheduler/ExecutionHistory.vue`

```
功能:
- 表格展示执行记录
- 筛选器 (任务/状态/日期范围)
- 点击行展开详情 (输出/错误信息)
- 重新执行按钮
```

**Day 4: 任务统计页面**

**文件**: `src/views/scheduler/TaskStatistics.vue`

```
功能:
- 成功率趋势图 (7天折线图)
- 任务执行分布饼图
- 任务执行排行 Top 10
- 失败原因分析饼图
```

**Day 5: 依赖图谱页面 (可选)**

**文件**: `src/views/scheduler/DependencyGraph.vue`

```
功能:
- 使用 @antv/g6 渲染 DAG 图
- 节点可点击查看详情
- 支持缩放/拖拽
```

#### 验收标准

- [ ] 任务列表 CRUD 完整 (增删改查)
- [ ] 触发/暂停/恢复按钮正常工作
- [ ] 执行历史能正确筛选和展开详情
- [ ] 统计图表正确渲染
- [ ] 新建任务表单验证完整

---

### WP-4: 技能中心 (Skills)

**负责人**: Agent D  
**工期**: 4 天  
**依赖**: WP-1  
**阻塞**: 无

#### 交付物

**Day 1: API 封装**

**文件**: `src/api/skills.ts`

```typescript
import client from './client'

export interface Skill {
  id: string
  name: string
  description: string
  category: string
  owner: string
  status: string
  current_version: string
  created_at: string
}

export interface SkillDetail extends Skill {
  content: string
  versions: SkillVersion[]
}

export interface SkillVersion {
  id: string
  version: string
  content_hash: string
  author: string
  commit_message: string
  created_at: string
}

export function listSkills(params?: { owner?: string; status?: string }) {
  return client.get('/skills', { params })
}

export function getSkill(id: string) {
  return client.get(`/skills/${id}`)
}

export function createSkill(data: Partial<Skill>) {
  return client.post('/skills', data)
}

export function updateSkill(id: string, data: Partial<Skill>) {
  return client.put(`/skills/${id}`, data)
}

export function deleteSkill(id: string) {
  return client.delete(`/skills/${id}`)
}
```

**Day 2: 技能列表页面**

**文件**: `src/views/skills/SkillList.vue`

```
功能:
- 表格展示技能 (名称/分类/版本/状态/所有者)
- 搜索 + 筛选
- 新建技能弹窗
- 删除确认
```

**Day 3: 版本历史页面**

**文件**: `src/views/skills/VersionHistory.vue`

```
功能:
- 时间线展示版本历史
- 版本对比 (diff)
- 回滚按钮
```

**Day 4: 技能编辑器页面**

**文件**: `src/views/skills/SkillEditor.vue`

```
功能:
- Monaco Editor 编辑 Markdown
- 实时预览 (Markdown 渲染)
- 提交信息输入
- 保存/取消按钮
```

#### 验收标准

- [ ] 技能列表展示正确
- [ ] 版本历史时间线渲染正确
- [ ] Monaco Editor 能正常编辑和预览
- [ ] 保存时弹出提交信息对话框

---

### WP-5: 事件中心 (Events) + WebSocket

**负责人**: Agent E  
**工期**: 4 天  
**依赖**: WP-1  
**阻塞**: 无

#### 交付物

**Day 1: WebSocket 封装**

**文件**: `src/composables/useEventStream.ts`

```typescript
import { ref, onMounted, onUnmounted } from 'vue'

export interface EventItem {
  type: string
  agent_id: string
  data: Record<string, any>
  timestamp: string
}

export function useEventStream(filters: string[] = []) {
  const events = ref<EventItem[]>([])
  const connected = ref(false)
  let ws: WebSocket | null = null

  const connect = () => {
    ws = new WebSocket(`ws://127.0.0.1:8081/ws/events?filters=${filters.join(',')}`)
    ws.onopen = () => { connected.value = true }
    ws.onmessage = (e) => {
      events.value.unshift(JSON.parse(e.data))
      if (events.value.length > 500) events.value.pop()
    }
    ws.onclose = () => { connected.value = false }
  }

  const disconnect = () => {
    ws?.close()
  }

  const clear = () => {
    events.value = []
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return { events, connected, connect, disconnect, clear }
}
```

**Day 2-3: 实时事件流页面**

**文件**: `src/views/events/EventStream.vue`

```
功能:
- WebSocket 连接状态指示
- 实时事件列表 (带颜色标识)
- 事件类型过滤器 (checkbox)
- 搜索框
- 暂停/继续按钮
- 清空按钮
- 导出按钮
```

**Day 4: 事件历史页面**

**文件**: `src/views/events/EventHistory.vue`

```
功能:
- 从 HTTP API 查询历史事件
- 分页 + 筛选
- 事件详情展开
```

#### 验收标准

- [ ] WebSocket 连接稳定
- [ ] 实时事件流显示正确
- [ ] 事件过滤器正常工作
- [ ] 暂停/继续功能正常
- [ ] 事件历史查询正常

---

### WP-6: 决策中心 (Decisions)

**负责人**: Agent F  
**工期**: 3 天  
**依赖**: WP-1  
**阻塞**: 无

#### 说明

决策中心目前只有 CLI 接口，**没有 HTTP API**。需要先确认是否需要添加 HTTP API，或者仅展示静态数据。

**方案 A** (推荐): 仅展示静态数据/占位页面
**方案 B**: 先让其他 Agent 给 Agent OS 添加 Decision HTTP API，再开发页面

#### 交付物 (方案 A)

**Day 1: 决策列表页面**

**文件**: `src/views/decisions/DecisionList.vue`

```
功能:
- 表格展示决策记录 (从 mock 数据)
- 筛选 (动作/Agent/日期/执行状态)
- 点击行展开详情
```

**Day 2: 决策统计页面**

**文件**: `src/views/decisions/DecisionStatistics.vue`

```
功能:
- 胜率趋势图
- 动作分布饼图
- 置信度校准图
```

**Day 3: 决策详情页面**

**文件**: `src/views/decisions/DecisionDetail.vue`

```
功能:
- 决策完整信息展示
- 执行结果展示
- 决策质量评分
```

#### 验收标准

- [ ] 决策列表展示正确 (mock 数据)
- [ ] 统计图表渲染正确
- [ ] 详情页面信息完整

---

### WP-7: 记忆中心 (Memory)

**负责人**: Agent G  
**工期**: 3 天  
**依赖**: WP-1  
**阻塞**: 无

#### 说明

记忆中心同样只有 CLI 接口，**没有 HTTP API**。采用与决策中心相同的方案。

#### 交付物

**Day 1: 记忆列表页面**

**文件**: `src/views/memory/MemoryList.vue`

```
功能:
- 卡片式展示记忆
- 搜索 + 分类筛选 + 标签筛选
- 重要性排序
- 新建/编辑/删除
```

**Day 2: 记忆搜索页面**

**文件**: `src/views/memory/MemorySearch.vue`

```
功能:
- 搜索框 (支持 BM25 + 向量搜索)
- 搜索结果列表 (带相关度分数)
- 筛选器 (分类/标签/重要性)
```

**Day 3: 标签管理页面**

**文件**: `src/views/memory/TagManagement.vue`

```
功能:
- 标签云展示
- 标签增删改
- 按标签查看记忆
```

#### 验收标准

- [ ] 记忆列表展示正确
- [ ] 搜索功能正常 (mock)
- [ ] 标签管理正常

---

### WP-8: 通知中心 (Notifications)

**负责人**: Agent H  
**工期**: 3 天  
**依赖**: WP-1  
**阻塞**: 无

#### 交付物

**Day 1: API 封装 + 渠道列表**

**文件**: `src/api/notifications.ts`

```typescript
import client from './client'

export function listChannels() {
  return client.get('/notifications/channels')
}

export function getLogs(limit = 50) {
  return client.get('/notifications/logs', { params: { limit } })
}

export function sendNotification(data: {
  channel: string
  title: string
  content: string
}) {
  return client.post('/notifications/send', data)
}
```

**文件**: `src/views/notifications/ChannelList.vue`

```
功能:
- 表格展示通知渠道
- 启用/禁用切换
- 测试发送按钮
```

**Day 2: 通知日志页面**

**文件**: `src/views/notifications/NotificationLogs.vue`

```
功能:
- 通知发送记录列表
- 状态筛选 (成功/失败)
- 重发按钮
```

**Day 3: 发送通知页面**

**文件**: `src/views/notifications/SendNotification.vue`

```
功能:
- 表单: 渠道/标题/内容
- 预览功能
- 发送按钮
```

#### 验收标准

- [ ] 渠道列表展示正确
- [ ] 通知日志查询正常
- [ ] 发送通知表单验证完整

---

### WP-9: 系统中心 (System)

**负责人**: Agent I  
**工期**: 3 天  
**依赖**: WP-1  
**阻塞**: 无

#### 交付物

**Day 1: 系统状态页面**

**文件**: `src/views/system/SystemStatus.vue`

```
功能:
- 服务健康状态卡片
- 系统资源使用 (CPU/MEM/DISK)
- 数据库连接池状态
- 最近系统日志
```

**Day 2: 资源配额页面**

**文件**: `src/views/system/ResourceQuotas.vue`

```
功能:
- 配额表格 (命名空间/资源类型/限制/已用/使用率)
- 使用率进度条
- 告警状态
```

**Day 3: API 文档 + 系统日志**

**文件**: `src/views/system/ApiDocs.vue`

```
功能:
- 嵌入 Swagger UI 或手动列出 API
```

**文件**: `src/views/system/SystemLogs.vue`

```
功能:
- 日志列表 (级别/时间/消息)
- 级别筛选
- 搜索
```

#### 验收标准

- [ ] 系统状态展示正确
- [ ] 资源配额表格正确
- [ ] API 文档可访问

---

### WP-10: 个人中心 (Profile) + 联调测试

**负责人**: Agent J  
**工期**: 4 天  
**依赖**: WP-1 ~ WP-9  
**阻塞**: 无

#### 交付物

**Day 1: 个人设置页面**

**文件**: `src/views/profile/ProfileSettings.vue`

```
功能:
- 基本信息表单
- 界面偏好 (主题/语言/每页条数)
- API 密钥管理
```

**Day 2: 操作记录页面**

**文件**: `src/views/profile/ActivityLog.vue`

```
功能:
- 用户操作记录列表
- 时间筛选
```

**Day 3-4: 联调测试**

**测试清单**:

| 测试项 | 方法 |
|--------|------|
| 启动 Agent OS | `go run cmd/agent-os/main.go serve` |
| 启动 Web | `npm run dev` |
| 概览页加载 | 访问 `/overview`，确认数据加载 |
| 任务 CRUD | 创建/读取/更新/删除任务 |
| 任务触发 | 点击触发按钮，确认 Webhook 调用 |
| WebSocket | 打开 Monitor 页面，确认实时事件 |
| 技能编辑 | 编辑技能，确认保存成功 |
| 响应式测试 | 移动端/平板/桌面端适配 |

#### 验收标准

- [ ] 所有页面能正常访问
- [ ] 核心功能 (任务 CRUD/触发/WebSocket) 工作正常
- [ ] 无明显 UI  bug
- [ ] 响应式适配完成

---

## 四、开发时序图

```
Week 1:
  Day 1-3:  WP-1 (脚手架) ───────────────────────────────┐
                                                          │
Week 2:                                                   │
  Day 4-7:  WP-2 (概览) ──────────────────┐               │
  Day 4-8:  WP-3 (调度) ──────────────────┼───┐           │
  Day 4-7:  WP-4 (技能) ──────────────────┼───┼───┐       │
  Day 4-7:  WP-5 (事件) ──────────────────┼───┼───┼───┐   │
                                          ↓   ↓   ↓   ↓   ↓
Week 3:                                   并行开发中...
  Day 8-10: WP-6 (决策) ──┐
  Day 8-10: WP-7 (记忆) ──┼───┐
  Day 8-10: WP-8 (通知) ──┼───┼───┐
                          ↓   ↓   ↓
Week 4:
  Day 11-13: WP-9 (系统) ─┐
                          ↓
Week 5-6:
  Day 14-17: WP-10 (联调) ────────────────────────────────┘
```

---

## 五、协作规范

### 5.1 代码规范

```
1. 使用 Vue 3 Composition API + <script setup>
2. 组件名使用 PascalCase (TaskList.vue)
3. 文件名使用 kebab-case (task-list.vue 不推荐)
4. API 函数放在 src/api/ 目录，按模块分文件
5. 类型定义放在 src/types/ 目录
6. 组件 props 使用 interface 定义
7. 使用 Element Plus 组件，避免手写 CSS
```

### 5.2 Git 工作流

```
1. 每个 WP 一个分支: feat/wp-2-overview, feat/wp-3-scheduler
2. 每日提交，commit message 用中文
3. WP 完成后发 PR 到 main
4. 由 Agent J (WP-10) 负责合并和冲突解决
```

### 5.3 接口约定

```typescript
// 列表响应统一格式
interface ListResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

// 错误响应统一格式
interface ErrorResponse {
  code: string
  message: string
  details?: Record<string, string[]>
}
```

---

## 六、风险与应对

| 风险 | 影响 | 应对方案 |
|------|------|----------|
| Agent OS 缺少某些 HTTP API | 页面无法获取数据 | 先实现 mock 数据，后续补 API |
| WebSocket 不稳定 | 实时事件中断 | 添加自动重连机制 |
| 多 Agent 代码冲突 | 合并困难 | 严格按模块划分，避免修改同一文件 |
| Element Plus 组件不满足需求 | UI 实现困难 | 使用自定义组件或换 Ant Design Vue |

---

## 七、验收标准 (总体)

- [ ] 28 个页面全部可访问
- [ ] 核心功能 (任务 CRUD/触发/暂停/恢复) 工作正常
- [ ] WebSocket 实时事件流稳定
- [ ] 响应式适配 (桌面/平板/手机)
- [ ] 无控制台报错
- [ ] `npm run build` 成功

---

**计划完成时间**: 2026-08-18  
**预计交付时间**: 6 周后 (2026-09-29)
