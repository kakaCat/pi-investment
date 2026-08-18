# Agent OS Web 面板 - 完善开发计划

> 本文档用于指导其他 agent 完成 Agent OS Web 面板的开发工作。
> 当前状态：MVP 阶段完成，大量功能缺失或仅使用 Mock 数据。
> 目标：完成设计文档中定义的全部 28 个页面。

---

## 一、项目结构速览

```
agent-os-web/                          # 前端项目根目录
├── src/
│   ├── api/                           # API 接口封装 (当前只有3个文件)
│   │   ├── overview.ts                # 概览相关 API
│   │   ├── scheduler.ts               # 调度器 API
│   │   └── skills.ts                  # 技能 API
│   ├── components/
│   │   └── layout/
│   │       ├── AppHeader.vue          # 顶部导航
│   │       ├── AppLayout.vue          # 布局框架
│   │       └── AppSidebar.vue         # 侧边栏 (当前只有一级菜单)
│   ├── views/                         # 页面视图
│   │   ├── overview/Dashboard.vue     # 系统总览 (部分数据为随机数)
│   │   ├── scheduler/TaskList.vue     # 任务列表 ✅
│   │   ├── scheduler/ExecutionHistory.vue  # 执行历史 ✅
│   │   ├── skills/SkillList.vue       # 技能列表 ✅
│   │   ├── decisions/DecisionList.vue # 决策列表 (纯 Mock)
│   │   ├── memory/MemoryList.vue      # 记忆列表 (纯 Mock)
│   │   ├── events/EventStream.vue     # 实时事件流 ✅
│   │   ├── system/SystemStatus.vue    # 系统状态 (静态数据)
│   │   └── NotFound.vue               # 404 页面 ✅
│   ├── router/index.ts                # 路由配置 (8 个路由)
│   ├── types/index.ts                 # TypeScript 类型定义
│   ├── utils/
│   │   ├── format.ts                  # 格式化工具 (时间/Cron)
│   │   └── request.ts                 # Axios 封装
│   ├── stores/                        # Pinia Store (空)
│   ├── composables/                   # 组合式函数 (空)
│   └── main.ts                        # 入口文件
├── vite.config.ts                     # Vite 配置 (含代理)
└── package.json
```

**Agent OS 后端** (Go, 端口 8080/8081):
```
api/v1/scheduler/tasks          GET/POST
api/v1/scheduler/tasks/{id}     PUT/DELETE
api/v1/scheduler/tasks/{id}/trigger  POST
api/v1/scheduler/tasks/{id}/pause    POST
api/v1/scheduler/tasks/{id}/resume   POST
api/v1/scheduler/executions     GET
api/v1/skills                   GET/POST
api/v1/skills/{id}              GET/PUT/DELETE
api/v1/notifications/channels   GET
api/v1/notifications/logs       GET
api/v1/notifications/send       POST
api/v1/notifications/providers  GET
/health                         GET
/ws/events                      WebSocket
```

---

## 二、任务清单（按优先级排序）

### 🔴 P0 - 阻塞修复（必须先完成）

#### 任务 1: Sidebar 二级菜单重构
**文件**: `src/components/layout/AppSidebar.vue`
**当前问题**: 只有 7 个一级菜单项，设计文档要求二级层级结构
**目标**: 实现二级菜单，与路由结构对齐

设计文档要求的菜单结构：
```
📊 概览中心
  ├── 系统总览 → /overview
  └── 实时监控 → /overview/monitor

⏰ 调度中心
  ├── 任务列表 → /scheduler/tasks
  ├── 执行历史 → /scheduler/executions
  ├── 任务统计 → /scheduler/statistics
  └── 依赖图谱 → /scheduler/dependencies

🧠 技能中心
  ├── 技能列表 → /skills
  ├── 版本历史 → /skills/:id/versions (动态)
  └── 技能编辑器 → /skills/:id/edit (动态)

📝 决策中心
  ├── 决策列表 → /decisions
  ├── 决策统计 → /decisions/statistics
  └── 决策详情 → /decisions/:id (动态)

💾 记忆中心
  ├── 记忆列表 → /memory
  ├── 记忆搜索 → /memory/search
  └── 标签管理 → /memory/tags

📡 事件中心
  ├── 实时事件流 → /events
  ├── 事件历史 → /events/history
  └── 告警规则 → /events/alerts

🔔 通知中心
  ├── 通知渠道 → /notifications/channels
  ├── 通知日志 → /notifications/logs
  └── 发送通知 → /notifications/send

⚙️ 系统中心
  ├── 系统状态 → /system/status
  ├── 资源配额 → /system/quotas
  ├── 命名空间 → /system/namespaces
  ├── API 文档 → /system/api-docs
  └── 系统日志 → /system/logs

👤 个人中心
  ├── 个人设置 → /profile
  └── 操作记录 → /profile/activity
```

**实现要点**:
- 使用 `el-sub-menu` 包裹二级菜单
- 一级菜单用图标 + 文字
- 当前激活项高亮
- 默认展开当前路由所在的一级菜单

---

#### 任务 2: 创建缺失的 API 文件
**目录**: `src/api/`
**当前状态**: 只有 `overview.ts`、`scheduler.ts`、`skills.ts`
**需要创建**:

**`src/api/decisions.ts`**:
```typescript
import client from '@/utils/request'

export const decisionApi = {
  list: (params?: { action?: string; status?: string; limit?: number }) =>
    client.get('/decisions', { params }),
  get: (id: string) => client.get(`/decisions/${id}`),
  getStatistics: () => client.get('/decisions/statistics'),
}
```

**`src/api/memory.ts`**:
```typescript
import client from '@/utils/request'

export const memoryApi = {
  list: (params?: { category?: string; tag?: string; limit?: number }) =>
    client.get('/memory', { params }),
  search: (q: string) => client.get('/memory/search', { params: { q } }),
  getTags: () => client.get('/memory/tags'),
  createTag: (name: string) => client.post('/memory/tags', { name }),
  deleteTag: (name: string) => client.delete(`/memory/tags/${name}`),
}
```

**`src/api/events.ts`**:
```typescript
import client from '@/utils/request'

export const eventApi = {
  getHistory: (params?: { type?: string; start?: string; end?: string; limit?: number }) =>
    client.get('/events/history', { params }),
  getAlertRules: () => client.get('/events/alerts'),
  createAlertRule: (data: any) => client.post('/events/alerts', data),
  deleteAlertRule: (id: string) => client.delete(`/events/alerts/${id}`),
}
```

**`src/api/notifications.ts`**:
```typescript
import client from '@/utils/request'

export const notificationApi = {
  getChannels: () => client.get('/notifications/channels'),
  getLogs: (params?: { limit?: number }) => client.get('/notifications/logs', { params }),
  send: (data: { channel: string; title: string; content: string }) =>
    client.post('/notifications/send', data),
  getProviders: () => client.get('/notifications/providers'),
}
```

**`src/api/system.ts`**:
```typescript
import client from '@/utils/request'

export const systemApi = {
  getStatus: () => client.get('/system/status'),
  getQuotas: () => client.get('/system/quotas'),
  getLogs: (params?: { limit?: number; level?: string }) =>
    client.get('/system/logs', { params }),
  getNamespaces: () => client.get('/system/namespaces'),
}
```

---

#### 任务 3: 路由配置补全
**文件**: `src/router/index.ts`
**当前**: 8 个路由
**需要添加的路由**:

```typescript
// 概览中心
{ path: 'overview/monitor', name: 'RealTimeMonitor', component: () => import('@/views/overview/Monitor.vue') }

// 调度中心
{ path: 'scheduler/statistics', name: 'TaskStatistics', component: () => import('@/views/scheduler/TaskStatistics.vue') }
{ path: 'scheduler/dependencies', name: 'DependencyGraph', component: () => import('@/views/scheduler/DependencyGraph.vue') }

// 技能中心
{ path: 'skills/:id/versions', name: 'VersionHistory', component: () => import('@/views/skills/VersionHistory.vue') }
{ path: 'skills/:id/edit', name: 'SkillEditor', component: () => import('@/views/skills/SkillEditor.vue') }

// 决策中心
{ path: 'decisions/statistics', name: 'DecisionStatistics', component: () => import('@/views/decisions/DecisionStatistics.vue') }
{ path: 'decisions/:id', name: 'DecisionDetail', component: () => import('@/views/decisions/DecisionDetail.vue') }

// 记忆中心
{ path: 'memory/search', name: 'MemorySearch', component: () => import('@/views/memory/MemorySearch.vue') }
{ path: 'memory/tags', name: 'TagManagement', component: () => import('@/views/memory/TagManagement.vue') }

// 事件中心
{ path: 'events/history', name: 'EventHistory', component: () => import('@/views/events/EventHistory.vue') }
{ path: 'events/alerts', name: 'AlertRules', component: () => import('@/views/events/AlertRules.vue') }

// 通知中心
{ path: 'notifications/channels', name: 'ChannelList', component: () => import('@/views/notifications/ChannelList.vue') }
{ path: 'notifications/logs', name: 'NotificationLogs', component: () => import('@/views/notifications/NotificationLogs.vue') }
{ path: 'notifications/send', name: 'SendNotification', component: () => import('@/views/notifications/SendNotification.vue') }

// 系统中心
{ path: 'system/quotas', name: 'ResourceQuotas', component: () => import('@/views/system/ResourceQuotas.vue') }
{ path: 'system/namespaces', name: 'Namespaces', component: () => import('@/views/system/Namespaces.vue') }
{ path: 'system/api-docs', name: 'ApiDocs', component: () => import('@/views/system/ApiDocs.vue') }
{ path: 'system/logs', name: 'SystemLogs', component: () => import('@/views/system/SystemLogs.vue') }

// 个人中心
{ path: 'profile', name: 'ProfileSettings', component: () => import('@/views/profile/ProfileSettings.vue') }
{ path: 'profile/activity', name: 'ActivityLog', component: () => import('@/views/profile/ActivityLog.vue') }
```

---

#### 任务 4: Overview 仪表盘数据真实化
**文件**: `src/views/overview/Dashboard.vue`
**当前问题**:
1. 24 小时趋势图使用 `Math.random()` 生成假数据
2. `successToday` 和 `failedToday` 硬编码为 0
3. 系统健康状态除 Agent OS API 外都是静态 "healthy"

**修复方案**:
1. 图表数据：从执行历史计算每小时的 success/failed 数量
2. 今日统计：遍历 executions，筛选 `started_at` 为今天的记录，按 status 计数
3. v2 API 健康：尝试调用一个轻量端点（如 `/health` 或 `/api/v1/scheduler/tasks?limit=1`）
4. 数据库健康：同上

**代码修改位置**:
```typescript
// 在 onMounted 中，获取任务列表后
const today = new Date().toISOString().split('T')[0]
const todayRuns = allExecutions.filter((e: any) => e.started_at?.startsWith(today))
stats.value.successToday = todayRuns.filter((e: any) => e.status === 'success').length
stats.value.failedToday = todayRuns.filter((e: any) => e.status === 'failed').length

// 图表数据：按小时聚合
const hourlyData = Array.from({ length: 24 }, (_, hour) => {
  const hourStr = String(hour).padStart(2, '0')
  const hourRuns = allExecutions.filter((e: any) => {
    const h = e.started_at?.split('T')[1]?.split(':')[0]
    return h === hourStr
  })
  return {
    success: hourRuns.filter((e: any) => e.status === 'success').length,
    failed: hourRuns.filter((e: any) => e.status === 'failed').length,
  }
})
chartOption.value.series[0].data = hourlyData.map(d => d.success)
chartOption.value.series[1].data = hourlyData.map(d => d.failed)
```

---

### 🟡 P1 - 核心功能页面

#### 任务 5: 实时监控页面
**文件**: `src/views/overview/Monitor.vue` (新建)
**设计文档**: 3.1 页面 2
**功能**:
- WebSocket 实时事件流（复用已有连接逻辑）
- 实时任务执行状态（运行中/排队中数量）
- 系统资源使用（CPU/内存/磁盘/网络）

**实现要点**:
- 复用 `EventStream.vue` 的 WebSocket 逻辑
- 添加事件过滤器（task/decision/memory/quota）
- 显示连接状态（已连接/已断开）
- 暂停/继续/清空按钮

---

#### 任务 6: 通知中心页面组
**新建文件**:
- `src/views/notifications/ChannelList.vue`
- `src/views/notifications/NotificationLogs.vue`
- `src/views/notifications/SendNotification.vue`

**ChannelList.vue**:
- 表格展示通知渠道（名称/类型/状态/配置/最近发送）
- 操作：编辑/删除
- 顶部按钮：添加渠道
- API: `GET /api/v1/notifications/channels`

**NotificationLogs.vue**:
- 表格展示通知发送记录
- 筛选：渠道/时间范围/状态
- API: `GET /api/v1/notifications/logs`

**SendNotification.vue**:
- 表单：渠道选择/标题/内容
- 发送按钮
- API: `POST /api/v1/notifications/send`

---

#### 任务 7: 个人设置页面
**文件**: `src/views/profile/ProfileSettings.vue` (新建)
**设计文档**: 3.9 页面 16
**功能**:
- 基本信息：用户名/邮箱/角色/时区
- 界面设置：主题（深色/浅色/自动）/语言/每页显示条数/自动刷新
- API 密钥：显示/重新生成/复制/撤销

**实现要点**:
- 使用 `el-form` 表单
- 主题切换使用 Element Plus 的 `dark` 模式
- 设置保存在 `localStorage`

---

#### 任务 8: 任务统计页面
**文件**: `src/views/scheduler/TaskStatistics.vue` (新建)
**设计文档**: 3.2 页面 5
**功能**:
- 成功率趋势（7 天折线图）
- 任务执行分布（饼图：成功/失败/超时/跳过）
- 任务执行排行（Top 10 表格）
- 失败原因分析（饼图）

**数据**: 从执行历史计算
**图表**: 使用 ECharts（已有依赖）

---

#### 任务 9: 决策中心真实化
**文件**: `src/views/decisions/DecisionList.vue`
**当前**: 纯 Mock 数据，显示 "Mock 数据" 标签
**修复**:
1. 移除 Mock 数据和警告提示
2. 接入 `decisionApi.list()`
3. 需要后端提供 `/api/v1/decisions` 端点

**如果后端暂不提供 API**:
- 保留当前 Mock 数据作为 fallback
- 但尝试调用 API，失败后才用 Mock

**新建文件**: `src/views/decisions/DecisionDetail.vue`
- 决策详情：动作/标的/置信度/理由/状态/PnL/时间线

---

#### 任务 10: 记忆中心真实化
**文件**: `src/views/memory/MemoryList.vue`
**当前**: 纯 Mock 数据
**修复**: 同决策中心，接入 `memoryApi.list()`

**新建文件**:
- `src/views/memory/MemorySearch.vue`: 搜索框 + 结果列表
- `src/views/memory/TagManagement.vue`: 标签 CRUD

---

#### 任务 11: 事件历史页面
**文件**: `src/views/events/EventHistory.vue` (新建)
**功能**:
- 历史事件查询（非实时）
- 筛选：事件类型/时间范围/Agent ID
- 分页表格
- API: `GET /api/v1/events/history` (需后端提供)

---

### 🟢 P2 - 高级功能

#### 任务 12: 技能版本历史
**文件**: `src/views/skills/VersionHistory.vue` (新建)
**设计文档**: 3.3 页面 8
**功能**:
- 时间线展示版本历史
- 版本号/作者/时间/提交消息/Hash
- 操作：回滚到此版本/查看差异/复制内容
- 数据：从 `GET /api/v1/skills/{id}` 返回的 versions 字段

---

#### 任务 13: 技能编辑器
**文件**: `src/views/skills/SkillEditor.vue` (新建)
**设计文档**: 3.3 页面 9
**功能**:
- 基本信息编辑：名称/分类/描述/所有者/状态
- Markdown 编辑器（可用 `el-input type="textarea"` 先实现基础版）
- 提交信息输入
- 保存/预览/放弃按钮
- API: `PUT /api/v1/skills/{id}`

---

#### 任务 14: 依赖图谱
**文件**: `src/views/scheduler/DependencyGraph.vue` (新建)
**设计文档**: 3.2 页面 6
**功能**:
- 交互式 DAG 图谱
- 节点：任务
- 边：依赖关系
- 点击节点查看详情
- 技术选型：D3.js 或 @antv/g6

**注意**: 这是大工作量任务，依赖关系数据需要后端支持。建议 P2 最后做。

---

#### 任务 15: 系统中心完善
**新建文件**:
- `src/views/system/ResourceQuotas.vue`: 资源配额表格（命名空间/资源类型/限制/已用/使用率）
- `src/views/system/Namespaces.vue`: 命名空间列表
- `src/views/system/ApiDocs.vue`: 嵌入 Swagger UI 或 API 列表
- `src/views/system/SystemLogs.vue`: 系统日志查看器

**注意**: 这些都需要后端 API 支持，当前 Agent OS 未提供。

---

#### 任务 16: 通用组件抽离
**目录**: `src/components/common/`
**需要创建的组件**:

| 组件 | 用途 | 优先级 |
|------|------|--------|
| `DataTable.vue` | 带排序/筛选/分页的表格 | P1 |
| `StatusBadge.vue` | 状态标签（成功/失败/警告/运行中） | P1 |
| `TimeAgo.vue` | 相对时间显示 | P2 |
| `CronDisplay.vue` | Cron 表达式中文显示 | P1 |
| `ChartCard.vue` | 图表卡片容器 | P1 |
| `MetricCard.vue` | 指标卡片（数字+趋势） | P1 |
| `EmptyState.vue` | 空状态提示 | P1 |

---

#### 任务 17: Pinia Store 接入
**目录**: `src/stores/`
**需要创建的 Store**:

**`src/stores/app.ts`**:
```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const theme = ref<'light' | 'dark' | 'auto'>('light')
  const language = ref('zh-CN')
  const pageSize = ref(20)
  const autoRefresh = ref(true)
  const refreshInterval = ref(30)

  return { theme, language, pageSize, autoRefresh, refreshInterval }
})
```

**`src/stores/scheduler.ts`**:
```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { schedulerApi } from '@/api/scheduler'
import type { Task, TaskRun } from '@/types'

export const useSchedulerStore = defineStore('scheduler', () => {
  const tasks = ref<Task[]>([])
  const executions = ref<TaskRun[]>([])
  const loading = ref(false)

  const fetchTasks = async () => {
    loading.value = true
    const result = await schedulerApi.listTasks()
    tasks.value = result.tasks || []
    loading.value = false
  }

  return { tasks, executions, loading, fetchTasks }
})
```

---

## 三、后端 API 缺口清单

以下 API 需要 Agent OS Go 后端新增。如果后端暂时无法提供，前端需要做好 fallback 处理：

| API | 方法 | 用途 | 优先级 |
|-----|------|------|--------|
| `/api/v1/decisions` | GET | 决策列表 | P1 |
| `/api/v1/decisions/{id}` | GET | 决策详情 | P1 |
| `/api/v1/decisions/statistics` | GET | 决策统计 | P2 |
| `/api/v1/memory` | GET | 记忆列表 | P1 |
| `/api/v1/memory/search` | GET | 记忆搜索 | P1 |
| `/api/v1/memory/tags` | GET/POST/DELETE | 标签管理 | P2 |
| `/api/v1/events/history` | GET | 事件历史 | P1 |
| `/api/v1/events/alerts` | GET/POST/DELETE | 告警规则 | P2 |
| `/api/v1/system/status` | GET | 系统状态 | P1 |
| `/api/v1/system/quotas` | GET | 资源配额 | P2 |
| `/api/v1/system/logs` | GET | 系统日志 | P2 |
| `/api/v1/system/namespaces` | GET | 命名空间 | P2 |

---

## 四、技术约束

1. **技术栈**: Vue 3 + TypeScript + Element Plus + Vue Router + Vite
2. **图表**: ECharts 5（已安装 `vue-echarts`）
3. **HTTP**: Axios（已封装在 `src/utils/request.ts`）
4. **代理**: 开发时 Vite 代理 `/api` 到 `http://127.0.0.1:8080`
5. **WebSocket**: 原生 WebSocket API，地址 `ws://127.0.0.1:8081/ws/events`
6. **样式**: Element Plus 默认样式 + scoped CSS

---

## 五、开发顺序建议

### 第一周：P0 修复 + P1 核心
1. 任务 1: Sidebar 二级菜单
2. 任务 2: 创建缺失 API 文件
3. 任务 3: 路由补全
4. 任务 4: Overview 数据真实化
5. 任务 5: 实时监控页面
6. 任务 6: 通知中心页面组
7. 任务 7: 个人设置页面

### 第二周：P1 完善
8. 任务 8: 任务统计页面
9. 任务 9: 决策中心真实化
10. 任务 10: 记忆中心真实化
11. 任务 11: 事件历史页面
12. 任务 16: 通用组件抽离（关键组件）

### 第三周：P2 高级
13. 任务 12: 技能版本历史
14. 任务 13: 技能编辑器
15. 任务 15: 系统中心完善
16. 任务 17: Pinia Store 接入

### 第四周：收尾
17. 任务 14: 依赖图谱（大工作量，放最后）
18. 测试和 Bug 修复
19. 性能优化

---

## 六、常见问题

### Q: 后端 API 返回什么格式？
A: Agent OS 后端返回统一格式：
```json
{
  "success": true,
  "data": { ... },
  "message": ""
}
```
Axios 拦截器已配置自动解包 `data` 字段。

### Q: 如何测试 API 是否可用？
A: 启动 Agent OS 后访问 `http://127.0.0.1:8080/health`，返回 `{"status":"ok"}` 即正常。

### Q: WebSocket 连接不上？
A: 检查 Agent OS WS 端口 8081 是否启动。开发时代码中地址为 `ws://127.0.0.1:8081/ws/events`。

### Q: 新增页面后路由不生效？
A: 确保在 `src/router/index.ts` 中添加了对应路由，且路径与 Sidebar 菜单的 `index` 一致。

### Q: Element Plus 图标怎么用？
A: 从 `@element-plus/icons-vue` 导入，例如：`import { Document, Loading } from '@element-plus/icons-vue'`

---

## 七、文件创建检查清单

执行开发前，确认以下文件存在：

```bash
# 检查现有文件
ls src/api/*.ts
ls src/views/*/*.vue
ls src/components/layout/*.vue
ls src/router/index.ts
ls src/types/index.ts
ls src/utils/*.ts

# 需要新建的目录
mkdir -p src/views/overview
mkdir -p src/views/scheduler
mkdir -p src/views/skills
mkdir -p src/views/decisions
mkdir -p src/views/memory
mkdir -p src/views/events
mkdir -p src/views/notifications
mkdir -p src/views/system
mkdir -p src/views/profile
mkdir -p src/components/common
mkdir -p src/stores
mkdir -p src/composables
```

---

**文档版本**: v1.0
**创建日期**: 2026-08-18
**对应设计文档**: `docs/superpowers/specs/agent-os-web-design.md`
