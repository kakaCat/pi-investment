# Registry 页面设计（最终简化版）

**核心原则**: 极简、清晰、只展示必要信息

---

## 📐 页面布局

### 主页面

```
┌─────────────────────────────────────────────────────┐
│  服务注册中心                                         │
│  当前 2 个服务在运行                       [刷新]     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ ✅ quantsys-v2                       💓 30秒前       │
│ ─────────────────────────────────────────────────── │
│ 交易系统 · 运行 10小时32分                          │
│ http://127.0.0.1:5001                               │
│                                                     │
│ [查看详情] [API 文档]                                │
├─────────────────────────────────────────────────────┤
│ ⏳ agent-dh                              未注册      │
│ ─────────────────────────────────────────────────── │
│ AI 决策大脑 · 待接入                                │
│                                                     │
│ [接入指南]                                           │
└─────────────────────────────────────────────────────┘
```

### 详情弹窗

```
┌─────────────────────────────────────┐
│ quantsys-v2 详情            [关闭]  │
├─────────────────────────────────────┤
│                                     │
│ 基本信息                             │
│ ─────────────────────────────────── │
│ Agent ID:  quantsys-v2-12345        │
│ 类型:      交易系统                  │
│ 状态:      ✅ 在线（空闲）           │
│ 版本:      v2.0                     │
│                                     │
│ 网络信息                             │
│ ─────────────────────────────────── │
│ 地址:      127.0.0.1:5001           │
│ API:       http://127.0.0.1:5001    │
│ 进程 ID:   12345                    │
│                                     │
│ 运行状态                             │
│ ─────────────────────────────────── │
│ 注册时间:  2024-08-19 10:00:00      │
│ 运行时长:  10小时32分钟              │
│ 最后心跳:  30秒前                    │
│                                     │
│ [打开 API 文档]                      │
└─────────────────────────────────────┘
```

---

## 📊 信息展示清单

### 卡片展示

| 信息 | 示例 | 说明 |
|------|------|------|
| **状态图标** | ✅ ⏳ ⚠️ | 绿色=在线，灰色=离线，黄色=异常 |
| **服务名称** | quantsys-v2 | 大字号，最显眼 |
| **心跳时间** | 💓 30秒前 | 右上角，判断健康 |
| **服务类型** | 交易系统 | 中文说明 |
| **运行时长** | 运行 10小时32分 | 判断稳定性 |
| **API 地址** | http://127.0.0.1:5001 | 点击可复制 |

### 详情弹窗

**基本信息**:
- Agent ID
- 类型
- 状态
- 版本

**网络信息**:
- 地址（host:port）
- API（完整 URL）
- 进程 ID

**运行状态**:
- 注册时间
- 运行时长
- 最后心跳

### 不展示的信息

- ❌ capabilities（能力列表）
- ❌ session_id
- ❌ metadata 原始数据
- ❌ 心跳历史

---

## 💻 完整代码

### 1. 类型定义

```typescript
// src/types/registry.ts

export interface Agent {
  id: string
  agent_id: string
  agent_type: string
  status: string
  host?: string
  port?: number
  pid?: number
  version?: string
  metadata?: {
    service?: string
    description?: string
    api_base?: string
    docs?: string
  }
  registered_at: string
  last_heartbeat_at: string
}
```

### 2. API 调用

```typescript
// src/api/registry.ts

import request from '@/utils/request'
import type { Agent } from '@/types/registry'

export function listAgents() {
  return request<Agent[]>({
    url: '/api/v1/registry/agents/available',
    method: 'get'
  })
}
```

### 3. 主页面

```vue
<!-- src/views/registry/AgentList.vue -->
<template>
  <div class="registry-page">
    <el-card shadow="never">
      <template #header>
        <div class="header">
          <div>
            <h2>服务注册中心</h2>
            <span class="subtitle">当前 {{ onlineCount }} 个服务在运行</span>
          </div>
          <el-button @click="refresh" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div v-loading="loading" class="agent-list">
        <agent-card
          v-for="agent in agents"
          :key="agent.agent_id"
          :agent="agent"
        />
        
        <!-- 空状态 -->
        <el-empty
          v-if="agents.length === 0 && !loading"
          description="暂无注册的服务"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listAgents } from '@/api/registry'
import AgentCard from './components/AgentCard.vue'
import type { Agent } from '@/types/registry'

const agents = ref<Agent[]>([])
const loading = ref(false)

const onlineCount = computed(() => agents.value.length)

async function loadAgents() {
  loading.value = true
  try {
    agents.value = await listAgents()
  } catch (error) {
    ElMessage.error('加载服务列表失败')
  } finally {
    loading.value = false
  }
}

function refresh() {
  loadAgents()
}

onMounted(() => {
  loadAgents()
})
</script>

<style scoped>
.registry-page {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h2 {
  margin: 0;
}

.subtitle {
  color: #909399;
  font-size: 14px;
}

.agent-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
```

### 4. Agent 卡片组件

```vue
<!-- src/views/registry/components/AgentCard.vue -->
<template>
  <el-card class="agent-card" :class="statusClass">
    <div class="agent-header">
      <el-badge :value="statusText" :type="statusType">
        <h3>{{ agent.agent_id }}</h3>
      </el-badge>
      <span class="heartbeat" :class="heartbeatClass">
        💓 {{ heartbeatText }}
      </span>
    </div>
    
    <div class="agent-info">
      <p>{{ agentTypeName }} · {{ uptimeText }}</p>
      <p class="api-url" @click="copyUrl" title="点击复制">
        {{ apiUrl }}
      </p>
    </div>
    
    <div class="actions">
      <el-button size="small" @click="showDetail">查看详情</el-button>
      <el-button size="small" @click="openDocs">API 文档</el-button>
    </div>
  </el-card>

  <!-- 详情弹窗 -->
  <el-dialog v-model="detailVisible" :title="`${agent.agent_id} 详情`" width="500px">
    <div class="detail-section">
      <h4>基本信息</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="Agent ID">
          {{ agent.agent_id }}
        </el-descriptions-item>
        <el-descriptions-item label="类型">
          {{ agentTypeName }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType" size="small">
            {{ statusText }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="版本">
          {{ agent.version || '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="detail-section">
      <h4>网络信息</h4>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="地址">
          {{ agent.host }}:{{ agent.port }}
        </el-descriptions-item>
        <el-descriptions-item label="API">
          <span class="clickable" @click="copyUrl">{{ apiUrl }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="进程 ID">
          {{ agent.pid || '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="detail-section">
      <h4>运行状态</h4>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="注册时间">
          {{ formatTime(agent.registered_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="运行时长">
          {{ uptimeText }}
        </el-descriptions-item>
        <el-descriptions-item label="最后心跳">
          {{ heartbeatText }}
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <template #footer>
      <el-button @click="detailVisible = false">关闭</el-button>
      <el-button type="primary" @click="openDocs">打开 API 文档</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { Agent } from '@/types/registry'

const props = defineProps<{
  agent: Agent
}>()

const detailVisible = ref(false)

// 计算心跳时间差（秒）
const heartbeatDiff = computed(() => {
  const now = Date.now()
  const last = new Date(props.agent.last_heartbeat_at).getTime()
  return Math.floor((now - last) / 1000)
})

// 状态类型
const statusType = computed(() => {
  const diff = heartbeatDiff.value
  if (diff < 60) return 'success'
  if (diff < 120) return 'warning'
  return 'danger'
})

// 状态文本
const statusText = computed(() => {
  const type = statusType.value
  const status = props.agent.status
  if (type === 'danger') return '离线'
  if (type === 'warning') return '异常'
  return status === 'busy' ? '忙碌' : '空闲'
})

// 状态 CSS 类
const statusClass = computed(() => {
  return `status-${statusType.value}`
})

// 心跳文本
const heartbeatText = computed(() => {
  const diff = heartbeatDiff.value
  if (diff < 60) return `${diff}秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  return `${Math.floor(diff / 3600)}小时前`
})

// 心跳 CSS 类
const heartbeatClass = computed(() => {
  return `heartbeat-${statusType.value}`
})

// 运行时长
const uptimeText = computed(() => {
  const now = Date.now()
  const registered = new Date(props.agent.registered_at).getTime()
  const diff = Math.floor((now - registered) / 1000)
  
  const hours = Math.floor(diff / 3600)
  const minutes = Math.floor((diff % 3600) / 60)
  
  if (hours === 0) return `运行 ${minutes}分钟`
  return `运行 ${hours}小时${minutes}分钟`
})

// Agent 类型名称
const agentTypeName = computed(() => {
  const typeMap: Record<string, string> = {
    'trading-system': '交易系统',
    'ai-agent': 'AI 决策大脑',
    'data-service': '数据服务'
  }
  return typeMap[props.agent.agent_type] || props.agent.agent_type
})

// API URL
const apiUrl = computed(() => {
  return props.agent.metadata?.api_base || `http://${props.agent.host}:${props.agent.port}`
})

// 复制 URL
function copyUrl() {
  navigator.clipboard.writeText(apiUrl.value)
  ElMessage.success('已复制到剪贴板')
}

// 显示详情
function showDetail() {
  detailVisible.value = true
}

// 打开文档
function openDocs() {
  const docsUrl = props.agent.metadata?.docs || `${apiUrl.value}/docs`
  window.open(docsUrl, '_blank')
}

// 格式化时间
function formatTime(time: string) {
  return new Date(time).toLocaleString('zh-CN')
}
</script>

<style scoped>
.agent-card {
  transition: all 0.3s;
}

.agent-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

.agent-card.status-success {
  border-left: 4px solid #67c23a;
}

.agent-card.status-warning {
  border-left: 4px solid #e6a23c;
}

.agent-card.status-danger {
  border-left: 4px solid #f56c6c;
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.agent-header h3 {
  margin: 0;
  font-size: 18px;
}

.heartbeat {
  font-size: 14px;
  font-weight: 500;
}

.heartbeat.heartbeat-success {
  color: #67c23a;
}

.heartbeat.heartbeat-warning {
  color: #e6a23c;
}

.heartbeat.heartbeat-danger {
  color: #f56c6c;
}

.agent-info {
  margin-bottom: 16px;
  font-size: 14px;
  color: #606266;
}

.agent-info p {
  margin: 4px 0;
}

.api-url {
  color: #409eff;
  cursor: pointer;
  user-select: all;
}

.api-url:hover {
  text-decoration: underline;
}

.actions {
  display: flex;
  gap: 8px;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #303133;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 8px;
}

.clickable {
  color: #409eff;
  cursor: pointer;
  user-select: all;
}

.clickable:hover {
  text-decoration: underline;
}
</style>
```

### 5. 路由配置

```typescript
// src/router/index.ts

{
  path: 'registry',
  name: 'Registry',
  component: () => import('@/views/registry/AgentList.vue'),
}
```

---

## ✅ 总结

### 最终设计（极简版）

**卡片展示**:
- ✅ 状态（绿/黄/红）
- ✅ 服务名称
- ✅ 心跳时间
- ✅ 类型 + 运行时长
- ✅ API 地址

**详情弹窗**:
- ✅ 基本信息（4项）
- ✅ 网络信息（3项）
- ✅ 运行状态（3项）

**不展示**:
- ❌ 能力列表（capabilities）
- ❌ 其他技术细节

### 工作量

- 类型定义: 0.5小时
- API 封装: 0.5小时
- 主页面: 0.5小时
- 卡片组件: 1.5小时
- 路由配置: 0.5小时
- 测试调试: 0.5小时

**总计**: **4小时**完成

---

**文档创建时间**: 2024-08-19  
**版本**: 3.0（极简版 - 不展示能力）
