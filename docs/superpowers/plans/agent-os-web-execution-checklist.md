# Agent OS Web 开发任务清单（执行版）

**给执行 Agent 的说明**：按以下清单逐项完成，每完成一项打勾。完成后通知验收 Agent。

---

## 前置检查（必须先做）

```bash
# 1. 确认你在正确的目录
cd /Users/yunpeng/pi-investment

# 2. 确认没有未提交的改动
git status

# 3. 创建 worktree（必须在隔离环境开发）
git worktree add .claude/worktrees/agent-os-web -b feat/agent-os-web
cd .claude/worktrees/agent-os-web
```

---

## WP-1: 项目脚手架（3天）

### Day 1: 初始化项目

**步骤 1.1**: 创建项目目录
```bash
mkdir -p agent-os-web
cd agent-os-web
```

**步骤 1.2**: 用 npm 初始化 Vue 3 项目
```bash
npm create vue@latest . -- --typescript --router --pinia --vitest
# 全部选 Yes（TypeScript/Vue Router/Pinia/Vitest）
```

**步骤 1.3**: 安装依赖包（**必须按顺序执行，一个都不能少**）
```bash
# 核心依赖
npm install vue@3
npm install vue-router@4
npm install pinia
npm install axios
npm install element-plus
npm install echarts
npm install vue-echarts
npm install monaco-editor
npm install @element-plus/icons-vue

# 开发依赖
npm install -D typescript
npm install -D @types/node
npm install -D sass
npm install -D vite
npm install -D @vitejs/plugin-vue
npm install -D vitest
```

**验证 1.3**: 确认 package.json 有这些依赖
```bash
grep -E "vue|axios|element-plus|echarts|pinia|monaco" package.json
# 应该输出所有上面列出的包
```

**步骤 1.4**: 配置 vite.config.ts（**复制以下内容，不要改路径**）
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3003,  // Agent OS Web 端口
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
})
```

**步骤 1.5**: 配置 tsconfig.json（**在 compilerOptions 里添加**）
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

### Day 2: 基础文件

**步骤 2.1**: 创建目录结构（**必须全部创建**）
```bash
mkdir -p src/{api,components/{common,layout,business},views,stores,composables,router,types,utils}
```

**步骤 2.2**: 创建 `src/utils/request.ts`（**复制以下代码，不要改**）
```typescript
import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080/api/v1',
  timeout: 30000,
})

client.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.message || err.message
    console.error('API Error:', msg)
    return Promise.reject(err)
  }
)

export default client
```

**步骤 2.3**: 创建 `src/utils/format.ts`（**复制以下代码**）
```typescript
// 时间格式化
export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

// 相对时间
export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  return `${Math.floor(hours / 24)}天前`
}

// Cron 转中文
export function cronToChinese(cron: string): string {
  if (!cron) return '-'
  const parts = cron.split(' ')
  if (parts.length === 6) parts.shift() // 去掉秒字段
  const [min, hour, day, month, week] = parts
  if (min === '0' && hour === '2' && day === '*' && month === '*' && week === '*') return '每天 02:00'
  if (min === '40' && hour === '17') return '工作日 17:40'
  if (min === '0' && hour === '9') return '工作日 09:00'
  return cron
}
```

**步骤 2.4**: 创建 `src/types/index.ts`（**复制以下代码**）
```typescript
// 任务类型
export interface Task {
  id: string
  name: string
  owner: string
  description?: string
  cron: string
  command?: string
  webhook_url?: string
  payload?: Record<string, any>
  timeout: number
  retry_count: number
  enabled: boolean
  created_at: string
  updated_at: string
}

// 任务执行记录
export interface TaskRun {
  id: string
  task_id: string
  status: string
  started_at: string
  finished_at?: string
  output?: string
  error?: string
}

// 技能类型
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

// 事件类型
export interface EventItem {
  type: string
  agent_id: string
  data: Record<string, any>
  timestamp: string
}
```

**步骤 2.5**: 创建 `src/stores/app.ts`（**复制以下代码**）
```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const theme = ref<'light' | 'dark'>('dark')
  
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }
  
  return { sidebarCollapsed, theme, toggleSidebar }
})
```

### Day 3: 布局组件

**步骤 3.1**: 创建 `src/components/layout/AppLayout.vue`（**复制以下代码**）
```vue
<template>
  <el-container class="app-layout">
    <AppSidebar />
    <el-container>
      <AppHeader />
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
</script>

<style scoped>
.app-layout {
  height: 100vh;
}
</style>
```

**步骤 3.2**: 创建 `src/components/layout/AppSidebar.vue`（**复制以下代码**）
```vue
<template>
  <el-aside width="200px" class="sidebar">
    <div class="logo">🧠 Agent OS</div>
    <el-menu
      :default-active="$route.path"
      router
      background-color="#1a1a2e"
      text-color="#fff"
      active-text-color="#409eff"
    >
      <el-menu-item index="/overview">
        <el-icon><DataLine /></el-icon>
        <span>概览中心</span>
      </el-menu-item>
      <el-menu-item index="/scheduler/tasks">
        <el-icon><Timer /></el-icon>
        <span>调度中心</span>
      </el-menu-item>
      <el-menu-item index="/skills">
        <el-icon><Brain /></el-icon>
        <span>技能中心</span>
      </el-menu-item>
      <el-menu-item index="/events">
        <el-icon><Bell /></el-icon>
        <span>事件中心</span>
      </el-menu-item>
      <el-menu-item index="/system/status">
        <el-icon><Setting /></el-icon>
        <span>系统中心</span>
      </el-menu-item>
    </el-menu>
  </el-aside>
</template>

<script setup lang="ts">
import { DataLine, Timer, Brain, Bell, Setting } from '@element-plus/icons-vue'
</script>

<style scoped>
.sidebar {
  background: #1a1a2e;
}
.logo {
  padding: 20px;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  text-align: center;
}
</style>
```

**步骤 3.3**: 创建 `src/components/layout/AppHeader.vue`（**复制以下代码**）
```vue
<template>
  <el-header class="header">
    <span>Agent OS 监控面板</span>
    <div class="right">
      <el-tag type="success">🟢 在线</el-tag>
      <span>admin</span>
    </div>
  </el-header>
</template>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #16213e;
  color: #fff;
}
.right {
  display: flex;
  gap: 12px;
  align-items: center;
}
</style>
```

**步骤 3.4**: 创建 `src/router/index.ts`（**复制以下代码**）
```typescript
import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppLayout,
      redirect: '/overview',
      children: [
        {
          path: 'overview',
          name: 'Overview',
          component: () => import('@/views/overview/Dashboard.vue'),
        },
        {
          path: 'scheduler/tasks',
          name: 'TaskList',
          component: () => import('@/views/scheduler/TaskList.vue'),
        },
        {
          path: 'skills',
          name: 'SkillList',
          component: () => import('@/views/skills/SkillList.vue'),
        },
        {
          path: 'events',
          name: 'EventStream',
          component: () => import('@/views/events/EventStream.vue'),
        },
        {
          path: 'system/status',
          name: 'SystemStatus',
          component: () => import('@/views/system/SystemStatus.vue'),
        },
      ],
    },
  ],
})

export default router
```

**步骤 3.5**: 修改 `src/main.ts`（**复制以下代码，完全替换**）
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'

const app = createApp(App)

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
```

**步骤 3.6**: 修改 `src/App.vue`（**复制以下代码，完全替换**）
```vue
<template>
  <router-view />
</template>
```

### WP-1 验收检查清单

执行以下命令验证：

```bash
# 1. 确认目录结构正确
ls src/{api,components,views,stores,router,types,utils}

# 2. 确认文件存在
ls src/utils/request.ts src/utils/format.ts src/types/index.ts
ls src/stores/app.ts src/router/index.ts src/components/layout/*.vue

# 3. 启动开发服务器
npm run dev

# 4. 在浏览器打开 http://localhost:3003
# 应该看到左侧有菜单，右侧空白（因为视图页面还没创建）
```

**必须全部通过才能进入 WP-2**

---

## WP-2: 概览中心（4天）

### Day 1: API 封装

**步骤 1.1**: 创建 `src/api/overview.ts`（**复制以下代码**）
```typescript
import client from './client'

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

### Day 2-3: Dashboard 页面

**步骤 2.1**: 创建 `src/views/overview/Dashboard.vue`

**要求**：
- 顶部 4 个卡片：总任务数 / 运行中 / 今日成功 / 今日失败
- 中间左侧：24h 执行趋势图（用 ECharts 折线图）
- 中间右侧：系统健康状态列表
- 底部：最近执行记录 Top 10

**必须使用的组件**：
- `el-card` - 卡片容器
- `el-statistic` - 数字统计
- `v-chart` (vue-echarts) - 图表
- `el-table` - 表格
- `el-tag` - 状态标签

**数据获取**：
```typescript
import { onMounted, ref } from 'vue'
import { getTaskStats, getSystemHealth, getRecentExecutions } from '@/api/overview'

const stats = ref({ total: 0, running: 0, successToday: 0, failedToday: 0 })
const health = ref({})
const recentRuns = ref([])

onMounted(async () => {
  try {
    stats.value = await getTaskStats()
    health.value = await getSystemHealth()
    recentRuns.value = await getRecentExecutions(10)
  } catch (e) {
    console.error('加载失败:', e)
  }
})
```

### Day 4: Monitor 页面

**步骤 3.1**: 创建 `src/views/overview/Monitor.vue`

**要求**：
- WebSocket 连接状态指示器（🟢 连接中 / 🔴 断开）
- 实时事件流列表（最多显示 100 条，新事件插入顶部）
- 事件类型过滤器（checkbox：task/decision/memory/quota）
- 暂停/继续按钮
- 清空按钮

**WebSocket 代码**：
```typescript
import { ref, onMounted, onUnmounted } from 'vue'

const events = ref([])
const connected = ref(false)
let ws = null

onMounted(() => {
  ws = new WebSocket('ws://127.0.0.1:8081/ws/events')
  ws.onopen = () => { connected.value = true }
  ws.onmessage = (e) => {
    events.value.unshift(JSON.parse(e.data))
    if (events.value.length > 100) events.value.pop()
  }
  ws.onclose = () => { connected.value = false }
})

onUnmounted(() => {
  ws?.close()
})
```

### WP-2 验收检查清单

```bash
# 1. 启动 Agent OS
cd agent-os && go run cmd/agent-os/main.go serve

# 2. 启动 Web
cd agent-os-web && npm run dev

# 3. 打开 http://localhost:3003/overview
# 验证：
# - 4 个指标卡片显示数字
# - 折线图渲染正常
# - 系统健康显示状态
# - 最近执行记录表格显示

# 4. 打开 http://localhost:3003/overview/monitor
# 验证：
# - WebSocket 状态 🟢
# - 事件列表实时更新
# - 过滤器正常工作
```

---

## WP-3: 调度中心（5天）

### Day 1: API 封装

**步骤 1.1**: 创建 `src/api/scheduler.ts`（**复制以下代码**）
```typescript
import client from './client'
import type { Task, TaskRun } from '@/types'

export const schedulerApi = {
  listTasks: (params?: any) => client.get('/scheduler/tasks', { params }),
  getTask: (id: string) => client.get(`/scheduler/tasks/${id}`),
  createTask: (data: any) => client.post('/scheduler/tasks', data),
  updateTask: (id: string, data: any) => client.put(`/scheduler/tasks/${id}`, data),
  deleteTask: (id: string) => client.delete(`/scheduler/tasks/${id}`),
  triggerTask: (id: string) => client.post(`/scheduler/tasks/${id}/trigger`),
  pauseTask: (id: string) => client.post(`/scheduler/tasks/${id}/pause`),
  resumeTask: (id: string) => client.post(`/scheduler/tasks/${id}/resume`),
  listExecutions: (params?: any) => client.get('/scheduler/executions', { params }),
}
```

### Day 2: 任务列表页面

**步骤 2.1**: 创建 `src/views/scheduler/TaskList.vue`

**要求**：
- 表格列：名称 / Cron / 状态 / 所有者 / 操作
- 搜索框（按名称过滤）
- 状态筛选（全部/启用/停用）
- 操作按钮：触发(▶️) / 暂停(⏸️) / 恢复(▶️) / 编辑(✏️) / 删除(🗑️)
- 新建任务按钮（弹出表单对话框）
- 分页

**新建任务表单字段**：
- 名称 (input, required)
- Cron (input, required, placeholder: "0 9 * * 1-5")
- Webhook URL (input)
- Payload (textarea, JSON)
- 超时 (number, default: 3600)
- 重试次数 (number, default: 0)
- 启用 (switch, default: true)

### Day 3: 执行历史页面

**步骤 3.1**: 创建 `src/views/scheduler/ExecutionHistory.vue`

**要求**：
- 表格列：执行ID / 任务名 / 状态 / 耗时 / 触发方式 / 时间
- 筛选：任务 / 状态 / 日期范围
- 点击行展开详情（输出/错误信息）
- 重新执行按钮

### Day 4: 任务统计页面

**步骤 4.1**: 创建 `src/views/scheduler/TaskStatistics.vue`

**要求**：
- 成功率趋势图（7天折线图）
- 任务执行分布饼图
- 任务执行排行 Top 10

### Day 5: 依赖图谱（可选，时间不够可跳过）

### WP-3 验收检查清单

```bash
# 1. 打开 http://localhost:3003/scheduler/tasks
# 验证：
# - 表格显示任务列表
# - 搜索框能过滤
# - 点击"触发"按钮，任务执行
# - 点击"新建"按钮，弹出表单，能创建任务
# - 点击"删除"按钮，有确认对话框

# 2. 打开 http://localhost:3003/scheduler/executions
# 验证：
# - 显示执行历史
# - 点击行展开详情
# - 筛选器正常工作

# 3. 打开 http://localhost:3003/scheduler/statistics
# 验证：
# - 图表渲染正常
```

---

## WP-4: 技能中心（4天）

### Day 1: API 封装

**步骤 1.1**: 创建 `src/api/skills.ts`
```typescript
import client from './client'

export const skillApi = {
  list: (params?: any) => client.get('/skills', { params }),
  get: (id: string) => client.get(`/skills/${id}`),
  create: (data: any) => client.post('/skills', data),
  update: (id: string, data: any) => client.put(`/skills/${id}`, data),
  delete: (id: string) => client.delete(`/skills/${id}`),
}
```

### Day 2: 技能列表

**步骤 2.1**: 创建 `src/views/skills/SkillList.vue`

**要求**：
- 表格：名称 / 分类 / 版本 / 状态 / 所有者 / 更新时间
- 搜索 + 分类筛选
- 新建技能按钮
- 删除确认

### Day 3: 版本历史

**步骤 3.1**: 创建 `src/views/skills/VersionHistory.vue`

**要求**：
- 时间线展示版本
- 显示：版本号 / 作者 / 时间 / 提交信息
- 回滚按钮

### Day 4: 技能编辑器

**步骤 4.1**: 创建 `src/views/skills/SkillEditor.vue`

**要求**：
- 左侧：Monaco Editor 编辑 Markdown
- 右侧：实时预览（用 markdown-it 渲染）
- 底部：提交信息输入框 + 保存按钮

**Monaco Editor 使用方式**：
```vue
<template>
  <div class="editor-container">
    <div ref="editorRef" class="editor"></div>
    <div class="preview" v-html="previewHtml"></div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as monaco from 'monaco-editor'

const editorRef = ref()
const content = ref('')
const previewHtml = ref('')

onMounted(() => {
  const editor = monaco.editor.create(editorRef.value, {
    value: '# 技能内容\n\n',
    language: 'markdown',
    theme: 'vs-dark',
  })
  editor.onDidChangeModelContent(() => {
    content.value = editor.getValue()
    // 更新预览
  })
})
</script>
```

### WP-4 验收检查清单

```bash
# 1. 打开 http://localhost:3003/skills
# 验证：
# - 技能列表显示
# - 能新建技能
# - 能删除技能

# 2. 点击技能名进入版本历史
# 验证：
# - 版本时间线显示

# 3. 点击编辑进入编辑器
# 验证：
# - Monaco Editor 能输入
# - 预览同步更新
# - 保存成功
```

---

## WP-5: 事件中心（4天）

### Day 1-2: 实时事件流

**步骤 1.1**: 创建 `src/views/events/EventStream.vue`

**要求**：
- WebSocket 连接（复用 WP-2 的代码）
- 事件列表（带颜色标识不同类型）
- 过滤器（checkbox：task/decision/memory/quota）
- 暂停/继续/清空按钮

**事件颜色映射**：
```typescript
const eventColors: Record<string, string> = {
  'task.started': '#409eff',
  'task.completed': '#67c23a',
  'task.failed': '#f56c6c',
  'decision.recorded': '#e6a23c',
  'memory.created': '#909399',
  'quota.warning': '#f56c6c',
}
```

### Day 3-4: 事件历史

**步骤 2.1**: 创建 `src/views/events/EventHistory.vue`

**要求**：
- 从 HTTP API 查询历史事件（mock 数据，因为 Agent OS 暂无事件历史 API）
- 分页 + 筛选
- 事件详情展开

### WP-5 验收检查清单

```bash
# 1. 打开 http://localhost:3003/events
# 验证：
# - WebSocket 连接成功
# - 事件实时显示
# - 过滤器正常工作
# - 暂停/继续/清空按钮正常

# 2. 打开 http://localhost:3003/events/history
# 验证：
# - 历史事件列表显示
```

---

## WP-6: 决策中心（3天）

**⚠️ 重要：Agent OS 目前没有 Decision HTTP API，使用 mock 数据**

### Day 1-3: Mock 页面

**步骤 1.1**: 创建 `src/views/decisions/DecisionList.vue`

**要求**：
- 表格展示 mock 决策数据
- 列：ID / 动作 / 标的 / 置信度 / 状态 / 盈亏
- 筛选器
- 点击展开详情

**Mock 数据**：
```typescript
const mockDecisions = [
  {
    id: '1',
    action: 'buy',
    targets: ['600519.SH'],
    confidence: 0.85,
    reason: 'ROE 25%，PE 历史30%分位',
    status: 'executed',
    pnl: '+5.2%',
    created_at: '2026-08-18T10:30:00Z',
  },
  // ... 更多 mock 数据
]
```

### WP-6 验收检查清单

```bash
# 打开 http://localhost:3003/decisions
# 验证：
# - 决策列表显示（mock 数据）
# - 筛选器正常工作
# - 详情展开正常
```

---

## WP-7: 记忆中心（3天）

**⚠️ 重要：Agent OS 目前没有 Memory HTTP API，使用 mock 数据**

### Day 1-3: Mock 页面

**步骤 1.1**: 创建 `src/views/memory/MemoryList.vue`

**要求**：
- 卡片式展示记忆
- 搜索 + 分类筛选
- 新建/编辑/删除

### WP-7 验收检查清单

```bash
# 打开 http://localhost:3003/memory
# 验证：
# - 记忆列表显示（mock 数据）
# - 搜索功能正常
```

---

## WP-8: 通知中心（3天）

### Day 1: API 封装 + 渠道列表

**步骤 1.1**: 创建 `src/api/notifications.ts`
```typescript
import client from './client'

export const notificationApi = {
  listChannels: () => client.get('/notifications/channels'),
  getLogs: (limit = 50) => client.get('/notifications/logs', { params: { limit } }),
  send: (data: any) => client.post('/notifications/send', data),
}
```

**步骤 1.2**: 创建 `src/views/notifications/ChannelList.vue`

### Day 2: 通知日志

**步骤 2.1**: 创建 `src/views/notifications/NotificationLogs.vue`

### Day 3: 发送通知

**步骤 3.1**: 创建 `src/views/notifications/SendNotification.vue`

### WP-8 验收检查清单

```bash
# 打开 http://localhost:3003/notifications/channels
# 验证：
# - 渠道列表显示
# - 发送通知表单正常
```

---

## WP-9: 系统中心（3天）

### Day 1: 系统状态

**步骤 1.1**: 创建 `src/views/system/SystemStatus.vue`

**要求**：
- 服务健康状态卡片
- 系统资源使用（CPU/MEM/DISK 进度条）
- 数据库连接池状态

### Day 2: 资源配额

**步骤 2.1**: 创建 `src/views/system/ResourceQuotas.vue`

### Day 3: API 文档 + 系统日志

**步骤 3.1**: 创建 `src/views/system/ApiDocs.vue`
- 简单列出所有 API 端点

**步骤 3.2**: 创建 `src/views/system/SystemLogs.vue`

### WP-9 验收检查清单

```bash
# 打开 http://localhost:3003/system/status
# 验证：
# - 系统状态显示
# - 资源使用进度条正常
```

---

## WP-10: 联调测试（4天）

### Day 1-2: 路由补全 + 空页面填充

**步骤 1.1**: 检查所有路由是否指向存在的页面

**步骤 1.2**: 为缺失的页面创建占位组件

### Day 3-4: 端到端测试

**测试清单**：

| # | 测试项 | 操作方法 | 预期结果 |
|---|--------|----------|----------|
| 1 | 启动 | `npm run dev` | 无报错，端口 3003 |
| 2 | 首页 | 访问 `/` | 重定向到 `/overview` |
| 3 | 概览 | 访问 `/overview` | 显示 4 个卡片 + 图表 |
| 4 | 监控 | 访问 `/overview/monitor` | WebSocket 连接成功 |
| 5 | 任务列表 | 访问 `/scheduler/tasks` | 显示任务表格 |
| 6 | 新建任务 | 点击"新建"按钮 | 弹出表单，能创建 |
| 7 | 触发任务 | 点击"触发"按钮 | 任务执行，状态变化 |
| 8 | 执行历史 | 访问 `/scheduler/executions` | 显示历史记录 |
| 9 | 技能列表 | 访问 `/skills` | 显示技能列表 |
| 10 | 事件流 | 访问 `/events` | WebSocket 实时更新 |
| 11 | 系统状态 | 访问 `/system/status` | 显示健康状态 |
| 12 | 构建 | `npm run build` | 成功，无报错 |

---

## 最终交付检查清单

### 代码提交

```bash
# 1. 确认所有文件已添加
git add -A

# 2. 提交
git commit -m "feat(agent-os-web): 完成监控面板开发

- 9 个一级菜单，28 个页面
- 任务调度 CRUD + 触发 + 统计
- Skill Hub 列表 + 版本 + 编辑器
- WebSocket 实时事件流
- 系统状态监控
- 响应式适配"

# 3. 合并回 main
git checkout main
git merge feat/agent-os-web
```

### 文件清单确认

```bash
# 必须存在的文件（逐项检查）
ls agent-os-web/package.json
ls agent-os-web/vite.config.ts
ls agent-os-web/src/main.ts
ls agent-os-web/src/App.vue
ls agent-os-web/src/router/index.ts
ls agent-os-web/src/utils/request.ts
ls agent-os-web/src/api/{overview,scheduler,skills,notifications}.ts
ls agent-os-web/src/views/overview/Dashboard.vue
ls agent-os-web/src/views/overview/Monitor.vue
ls agent-os-web/src/views/scheduler/TaskList.vue
ls agent-os-web/src/views/scheduler/ExecutionHistory.vue
ls agent-os-web/src/views/skills/SkillList.vue
ls agent-os-web/src/views/skills/SkillEditor.vue
ls agent-os-web/src/views/events/EventStream.vue
ls agent-os-web/src/views/system/SystemStatus.vue
```

---

## 常见错误预防

| 错误 | 预防方法 |
|------|----------|
| 路径别名 `@/` 不生效 | 确认 vite.config.ts 和 tsconfig.json 都配置了 alias |
| Element Plus 样式丢失 | 确认 main.ts 导入了 `element-plus/dist/index.css` |
| WebSocket 连接失败 | 确认端口是 8081，不是 8080 |
| API 404 | 确认 baseURL 是 `http://127.0.0.1:8080/api/v1` |
| 图标不显示 | 确认注册了 `@element-plus/icons-vue` |
| 路由跳转空白 | 确认路由配置的 component 路径正确 |
| TypeScript 报错 | 确认所有 .vue 文件有 `<script setup lang="ts">` |

---

**执行 Agent 完成所有任务后，通知验收 Agent 进行验收。**
