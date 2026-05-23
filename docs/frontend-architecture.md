# 量化交易系统前端架构设计

## 1. 架构概述

### 1.1 设计原则

本架构遵循**三层分离**原则，确保代码职责清晰、可维护性强：

- **展示层（Presentation Layer）**：纯UI组件，只负责渲染和用户交互
- **逻辑层（Business Logic Layer）**：业务逻辑、状态管理、数据处理
- **数据层（Data Layer）**：API调用、数据持久化、实时数据连接

### 1.2 核心特性

- **双模式支持**：Agent自动化模式 + 人工操作模式
- **实时数据**：WebSocket实时行情、信号推送
- **复杂图表**：K线图、买卖点标注、技术指标叠加
- **审批工作流**：Agent决策审批、复现验证
- **高性能**：虚拟滚动、按需加载、图表优化

## 2. 技术栈选择

### 2.1 核心框架

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | 3.4+ | 前端框架（Composition API） |
| TypeScript | 5.0+ | 类型安全 |
| Vite | 5.0+ | 构建工具 |
| Pinia | 2.1+ | 状态管理 |
| Vue Router | 4.0+ | 路由管理 |

### 2.2 UI与可视化

| 技术 | 版本 | 用途 |
|------|------|------|
| Element Plus | 2.7+ | UI组件库 |
| ECharts | 5.5+ | 图表库（K线、技术指标） |
| TradingView Lightweight Charts | 4.1+ | 专业K线图（备选） |
| Tailwind CSS | 3.4+ | 样式工具 |

### 2.3 数据与通信

| 技术 | 版本 | 用途 |
|------|------|------|
| Axios | 1.6+ | HTTP客户端 |
| Socket.IO Client | 4.7+ | WebSocket实时通信 |
| Day.js | 1.11+ | 日期处理 |
| Lodash-es | 4.17+ | 工具函数 |

### 2.4 开发与测试

| 技术 | 版本 | 用途 |
|------|------|------|
| ESLint | 8.0+ | 代码检查 |
| Prettier | 3.0+ | 代码格式化 |
| Vitest | 1.0+ | 单元测试 |
| Playwright | 1.40+ | E2E测试 |

## 3. 项目目录结构

```
web-frontend/
├── public/                    # 静态资源
│   ├── favicon.ico
│   └── logo.png
├── src/
│   ├── assets/               # 资源文件
│   │   ├── images/
│   │   ├── icons/
│   │   └── styles/
│   │       ├── variables.css  # CSS变量
│   │       ├── global.css     # 全局样式
│   │       └── themes/        # 主题配置
│   │
│   ├── components/           # 【展示层】UI组件
│   │   ├── common/           # 通用组件
│   │   │   ├── Button/
│   │   │   ├── Card/
│   │   │   ├── Table/
│   │   │   └── Modal/
│   │   ├── charts/           # 图表组件
│   │   │   ├── KLineChart/   # K线图
│   │   │   ├── LineChart/    # 折线图
│   │   │   ├── BarChart/     # 柱状图
│   │   │   └── HeatMap/      # 热力图
│   │   ├── trading/          # 交易相关组件
│   │   │   ├── SignalCard/   # 信号卡片
│   │   │   ├── OrderForm/    # 订单表单
│   │   │   └── PositionTable/ # 持仓表格
│   │   └── layout/           # 布局组件
│   │       ├── Header/
│   │       ├── Sidebar/
│   │       └── Footer/
│   │
│   ├── views/                # 【展示层】页面视图
│   │   ├── Dashboard/        # 仪表盘
│   │   ├── IndicatorIDE/     # 指标IDE
│   │   ├── StockResearch/    # 股票研究
│   │   ├── FactorAnalysis/   # 因子分析
│   │   ├── TradingSignals/   # 交易信号
│   │   ├── OpportunityRadar/ # 机会雷达
│   │   ├── Backtest/         # 回测与快速交易
│   │   ├── Portfolio/        # 持仓管理
│   │   ├── Orders/           # 订单管理
│   │   ├── Risk/             # 风控检查
│   │   ├── StrategyCenter/   # 策略运营中心
│   │   ├── MLEngine/         # ML引擎
│   │   └── AgentWorklog/     # Agent工作日志
│   │
│   ├── composables/          # 【逻辑层】组合式函数
│   │   ├── useChart.ts       # 图表逻辑
│   │   ├── useWebSocket.ts   # WebSocket连接
│   │   ├── usePolling.ts     # 轮询逻辑
│   │   ├── useTable.ts       # 表格逻辑
│   │   └── useForm.ts        # 表单逻辑
│   │
│   ├── stores/               # 【逻辑层】状态管理（Pinia）
│   │   ├── user.ts           # 用户状态
│   │   ├── market.ts         # 市场数据
│   │   ├── portfolio.ts      # 持仓状态
│   │   ├── signals.ts        # 信号状态
│   │   ├── agent.ts          # Agent状态
│   │   └── ui.ts             # UI状态（主题、侧边栏等）
│   │
│   ├── services/             # 【数据层】API服务
│   │   ├── api/              # HTTP API
│   │   │   ├── market.ts     # 市场数据API
│   │   │   ├── stock.ts      # 股票数据API
│   │   │   ├── trading.ts    # 交易API
│   │   │   ├── analysis.ts   # 分析API
│   │   │   ├── agent.ts      # Agent API
│   │   │   └── risk.ts       # 风控API
│   │   ├── websocket/        # WebSocket服务
│   │   │   ├── market.ts     # 实时行情
│   │   │   ├── signal.ts     # 实时信号
│   │   │   └── agent.ts      # Agent活动
│   │   └── storage/          # 本地存储
│   │       ├── localStorage.ts
│   │       └── indexedDB.ts
│   │
│   ├── utils/                # 工具函数
│   │   ├── format.ts         # 格式化（数字、日期）
│   │   ├── validate.ts       # 验证函数
│   │   ├── calculate.ts      # 计算函数
│   │   └── constants.ts      # 常量定义
│   │
│   ├── types/                # TypeScript类型定义
│   │   ├── api.ts            # API类型
│   │   ├── models.ts         # 数据模型
│   │   ├── components.ts     # 组件类型
│   │   └── enums.ts          # 枚举类型
│   │
│   ├── router/               # 路由配置
│   │   ├── index.ts
│   │   └── guards.ts         # 路由守卫
│   │
│   ├── App.vue               # 根组件
│   └── main.ts               # 入口文件
│
├── tests/                    # 测试文件
│   ├── unit/                 # 单元测试
│   └── e2e/                  # E2E测试
│
├── .env.development          # 开发环境变量
├── .env.production           # 生产环境变量
├── vite.config.ts            # Vite配置
├── tsconfig.json             # TypeScript配置
├── package.json
└── README.md
```

## 4. 三层架构详细设计

### 4.1 展示层（Presentation Layer）

**职责**：纯UI渲染，不包含业务逻辑

#### 4.1.1 组件设计原则

- **单一职责**：每个组件只做一件事
- **Props Down, Events Up**：通过props接收数据，通过events向上传递事件
- **无状态优先**：优先使用无状态组件，状态由父组件或store管理
- **可复用性**：通用组件高度抽象，业务组件专注特定场景

#### 4.1.2 组件分类

**1. 通用组件（components/common/）**

```typescript
// Button组件示例
<template>
  <button 
    :class="buttonClass" 
    :disabled="disabled"
    @click="handleClick"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
interface Props {
  type?: 'primary' | 'success' | 'warning' | 'danger'
  size?: 'small' | 'medium' | 'large'
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  type: 'primary',
  size: 'medium',
  disabled: false
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const handleClick = (e: MouseEvent) => {
  if (!props.disabled) {
    emit('click', e)
  }
}
</script>
```

**2. 图表组件（components/charts/）**

```typescript
// KLineChart组件示例
<template>
  <div ref="chartRef" class="kline-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { KLineData, TradingSignal } from '@/types/models'

interface Props {
  data: KLineData[]
  signals?: TradingSignal[]
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  height: '500px'
})

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

onMounted(() => {
  initChart()
})

watch(() => props.data, () => {
  updateChart()
})

const initChart = () => {
  // 图表初始化逻辑（纯渲染，不包含数据获取）
}

const updateChart = () => {
  // 图表更新逻辑
}
</script>
```

**3. 业务组件（components/trading/）**

```typescript
// SignalCard组件示例
<template>
  <Card>
    <div class="signal-card">
      <div class="signal-header">
        <span :class="signalTypeClass">{{ signal.type }}</span>
        <span class="confidence">置信度: {{ signal.confidence }}%</span>
      </div>
      <div class="signal-body">
        <p>股票: {{ signal.symbol }}</p>
        <p>价格: {{ formatPrice(signal.price) }}</p>
        <p>原因: {{ signal.reasons.join(', ') }}</p>
      </div>
      <div class="signal-actions">
        <Button @click="emit('approve', signal.id)">批准</Button>
        <Button @click="emit('reject', signal.id)">拒绝</Button>
        <Button @click="emit('verify', signal.id)">复现验证</Button>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import type { TradingSignal } from '@/types/models'

interface Props {
  signal: TradingSignal
}

const props = defineProps<Props>()

const emit = defineEmits<{
  approve: [signalId: string]
  reject: [signalId: string]
  verify: [signalId: string]
}>()
</script>
```

#### 4.1.3 页面视图（views/）

页面视图负责组合组件，协调展示层和逻辑层：

```typescript
// views/TradingSignals/index.vue
<template>
  <div class="trading-signals-page">
    <PageHeader title="交易信号" />
    
    <FilterBar 
      v-model:filters="filters"
      @search="handleSearch"
    />
    
    <div class="signals-grid">
      <SignalCard
        v-for="signal in signals"
        :key="signal.id"
        :signal="signal"
        @approve="handleApprove"
        @reject="handleReject"
        @verify="handleVerify"
      />
    </div>
    
    <Pagination
      v-model:page="currentPage"
      :total="totalSignals"
      @change="loadSignals"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSignalStore } from '@/stores/signals'
import { useSignalActions } from '@/composables/useSignalActions'

// 使用store获取状态
const signalStore = useSignalStore()
const { signals, totalSignals } = storeToRefs(signalStore)

// 使用composable处理业务逻辑
const { approveSignal, rejectSignal, verifySignal } = useSignalActions()

// 本地UI状态
const filters = ref({})
const currentPage = ref(1)

onMounted(() => {
  loadSignals()
})

const loadSignals = () => {
  signalStore.fetchSignals({ page: currentPage.value, ...filters.value })
}

const handleApprove = (signalId: string) => {
  approveSignal(signalId)
}

const handleReject = (signalId: string) => {
  rejectSignal(signalId)
}

const handleVerify = (signalId: string) => {
  verifySignal(signalId)
}
</script>
```

### 4.2 逻辑层（Business Logic Layer）

**职责**：业务逻辑、状态管理、数据处理

#### 4.2.1 状态管理（Pinia Stores）

**设计原则**：
- 按业务领域划分store
- 每个store只管理相关状态
- 使用actions处理异步操作
- 使用getters计算派生状态

```typescript
// stores/signals.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { signalApi } from '@/services/api/signal'
import type { TradingSignal, SignalFilters } from '@/types/models'

export const useSignalStore = defineStore('signals', () => {
  // State
  const signals = ref<TradingSignal[]>([])
  const currentSignal = ref<TradingSignal | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  
  // Getters
  const pendingSignals = computed(() => 
    signals.value.filter(s => s.status === 'pending')
  )
  
  const approvedSignals = computed(() =>
    signals.value.filter(s => s.status === 'approved')
  )
  
  const signalStats = computed(() => ({
    total: signals.value.length,
    pending: pendingSignals.value.length,
    approved: approvedSignals.value.length,
    avgConfidence: signals.value.reduce((sum, s) => sum + s.confidence, 0) / signals.value.length
  }))
  
  // Actions
  const fetchSignals = async (filters?: SignalFilters) => {
    loading.value = true
    error.value = null
    try {
      const data = await signalApi.getSignals(filters)
      signals.value = data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  
  const approveSignal = async (signalId: string) => {
    try {
      await signalApi.approveSignal(signalId)
      const signal = signals.value.find(s => s.id === signalId)
      if (signal) {
        signal.status = 'approved'
      }
    } catch (e) {
      error.value = e.message
    }
  }
  
  const rejectSignal = async (signalId: string, reason: string) => {
    try {
      await signalApi.rejectSignal(signalId, reason)
      const signal = signals.value.find(s => s.id === signalId)
      if (signal) {
        signal.status = 'rejected'
      }
    } catch (e) {
      error.value = e.message
    }
  }
  
  return {
    // State
    signals,
    currentSignal,
    loading,
    error,
    // Getters
    pendingSignals,
    approvedSignals,
    signalStats,
    // Actions
    fetchSignals,
    approveSignal,
    rejectSignal
  }
})
```

#### 4.2.2 组合式函数（Composables）

**设计原则**：
- 封装可复用的业务逻辑
- 处理副作用（API调用、定时器、事件监听）
- 返回响应式状态和方法

```typescript
// composables/useSignalActions.ts
import { ref } from 'vue'
import { useSignalStore } from '@/stores/signals'
import { ElMessage, ElMessageBox } from 'element-plus'

export function useSignalActions() {
  const signalStore = useSignalStore()
  const processing = ref(false)
  
  const approveSignal = async (signalId: string) => {
    try {
      await ElMessageBox.confirm('确认批准此信号？', '提示')
      processing.value = true
      await signalStore.approveSignal(signalId)
      ElMessage.success('信号已批准')
    } catch (e) {
      if (e !== 'cancel') {
        ElMessage.error('批准失败: ' + e.message)
      }
    } finally {
      processing.value = false
    }
  }
  
  const rejectSignal = async (signalId: string) => {
    try {
      const { value: reason } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝信号')
      processing.value = true
      await signalStore.rejectSignal(signalId, reason)
      ElMessage.success('信号已拒绝')
    } catch (e) {
      if (e !== 'cancel') {
        ElMessage.error('拒绝失败: ' + e.message)
      }
    } finally {
      processing.value = false
    }
  }
  
  const verifySignal = async (signalId: string) => {
    // 打开复现验证页面
    router.push({ name: 'SignalVerify', params: { id: signalId } })
  }
  
  return {
    processing,
    approveSignal,
    rejectSignal,
    verifySignal
  }
}
```

```typescript
// composables/useWebSocket.ts
import { ref, onMounted, onUnmounted } from 'vue'
import { io, Socket } from 'socket.io-client'

export function useWebSocket(url: string) {
  const socket = ref<Socket | null>(null)
  const connected = ref(false)
  const error = ref<string | null>(null)
  
  const connect = () => {
    socket.value = io(url, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    })
    
    socket.value.on('connect', () => {
      connected.value = true
      error.value = null
    })
    
    socket.value.on('disconnect', () => {
      connected.value = false
    })
    
    socket.value.on('error', (err) => {
      error.value = err.message
    })
  }
  
  const disconnect = () => {
    socket.value?.disconnect()
  }
  
  const emit = (event: string, data: any) => {
    socket.value?.emit(event, data)
  }
  
  const on = (event: string, callback: (...args: any[]) => void) => {
    socket.value?.on(event, callback)
  }
  
  onMounted(() => {
    connect()
  })
  
  onUnmounted(() => {
    disconnect()
  })
  
  return {
    socket,
    connected,
    error,
    emit,
    on,
    connect,
    disconnect
  }
}
```

### 4.3 数据层（Data Layer）

**职责**：API调用、数据持久化、实时数据连接

#### 4.3.1 HTTP API服务

**设计原则**：
- 统一的请求/响应拦截器
- 错误处理和重试机制
- 请求取消和超时控制
- 类型安全的API接口

```typescript
// services/api/client.ts
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

class ApiClient {
  private instance: AxiosInstance
  
  constructor(baseURL: string) {
    this.instance = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    this.setupInterceptors()
  }
  
  private setupInterceptors() {
    // 请求拦截器
    this.instance.interceptors.request.use(
      (config) => {
        const userStore = useUserStore()
        if (userStore.token) {
          config.headers.Authorization = `Bearer ${userStore.token}`
        }
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )
    
    // 响应拦截器
    this.instance.interceptors.response.use(
      (response) => {
        return response.data
      },
      (error) => {
        if (error.response) {
          const { status, data } = error.response
          
          switch (status) {
            case 401:
              ElMessage.error('未授权，请重新登录')
              // 跳转到登录页
              break
            case 403:
              ElMessage.error('没有权限访问')
              break
            case 404:
              ElMessage.error('请求的资源不存在')
              break
            case 500:
              ElMessage.error('服务器错误')
              break
            default:
              ElMessage.error(data.message || '请求失败')
          }
        } else if (error.request) {
          ElMessage.error('网络错误，请检查网络连接')
        }
        
        return Promise.reject(error)
      }
    )
  }
  
  public get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.get(url, config)
  }
  
  public post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.post(url, data, config)
  }
  
  public put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.put(url, data, config)
  }
  
  public delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.delete(url, config)
  }
}

export const apiClient = new ApiClient(import.meta.env.VITE_API_BASE_URL)
```

```typescript
// services/api/signal.ts
import { apiClient } from './client'
import type { TradingSignal, SignalFilters, SignalStatistics } from '@/types/models'

export const signalApi = {
  // 获取信号列表
  getSignals(filters?: SignalFilters) {
    return apiClient.get<TradingSignal[]>('/api/signals', { params: filters })
  },
  
  // 获取单个信号详情
  getSignalById(id: string) {
    return apiClient.get<TradingSignal>(`/api/signals/${id}`)
  },
  
  // 批准信号
  approveSignal(id: string) {
    return apiClient.post(`/api/signals/${id}/approve`)
  },
  
  // 拒绝信号
  rejectSignal(id: string, reason: string) {
    return apiClient.post(`/api/signals/${id}/reject`, { reason })
  },
  
  // 标记错误信号
  markError(id: string, errorType: string) {
    return apiClient.post(`/api/signals/${id}/mark-error`, { errorType })
  },
  
  // 获取信号统计
  getStatistics(dateRange?: { start: string; end: string }) {
    return apiClient.get<SignalStatistics>('/api/signals/statistics', { params: dateRange })
  }
}
```

#### 4.3.2 WebSocket服务

```typescript
// services/websocket/market.ts
import { io, Socket } from 'socket.io-client'
import type { RealtimeQuote } from '@/types/models'

class MarketWebSocket {
  private socket: Socket | null = null
  private subscribers: Map<string, Set<(data: any) => void>> = new Map()
  
  connect() {
    this.socket = io(import.meta.env.VITE_WS_URL, {
      transports: ['websocket'],
      reconnection: true
    })
    
    this.socket.on('connect', () => {
      console.log('Market WebSocket connected')
    })
    
    this.socket.on('quote', (data: RealtimeQuote) => {
      this.notify('quote', data)
    })
    
    this.socket.on('signal', (data: any) => {
      this.notify('signal', data)
    })
  }
  
  disconnect() {
    this.socket?.disconnect()
  }
  
  subscribe(event: string, callback: (data: any) => void) {
    if (!this.subscribers.has(event)) {
      this.subscribers.set(event, new Set())
    }
    this.subscribers.get(event)!.add(callback)
  }
  
  unsubscribe(event: string, callback: (data: any) => void) {
    this.subscribers.get(event)?.delete(callback)
  }
  
  private notify(event: string, data: any) {
    this.subscribers.get(event)?.forEach(callback => callback(data))
  }
  
  subscribeSymbol(symbol: string) {
    this.socket?.emit('subscribe', { symbol })
  }
  
  unsubscribeSymbol(symbol: string) {
    this.socket?.emit('unsubscribe', { symbol })
  }
}

export const marketWs = new MarketWebSocket()
```

#### 4.3.3 本地存储服务

```typescript
// services/storage/localStorage.ts
class LocalStorage {
  set<T>(key: string, value: T): void {
    try {
      const serialized = JSON.stringify(value)
      localStorage.setItem(key, serialized)
    } catch (e) {
      console.error('LocalStorage set error:', e)
    }
  }
  
  get<T>(key: string, defaultValue?: T): T | null {
    try {
      const item = localStorage.getItem(key)
      return item ? JSON.parse(item) : defaultValue ?? null
    } catch (e) {
      console.error('LocalStorage get error:', e)
      return defaultValue ?? null
    }
  }
  
  remove(key: string): void {
    localStorage.removeItem(key)
  }
  
  clear(): void {
    localStorage.clear()
  }
}

export const storage = new LocalStorage()
```

## 5. 数据流设计

### 5.1 单向数据流

```
用户操作 → 触发事件 → 调用Action → 更新Store → 响应式更新View
```

### 5.2 实时数据流

```
WebSocket → 接收数据 → 更新Store → 响应式更新图表/列表
```

### 5.3 完整数据流示例

```typescript
// 用户点击"批准信号"按钮的完整数据流

// 1. 展示层：用户点击按钮
<SignalCard @approve="handleApprove" />

// 2. 视图层：处理事件
const handleApprove = (signalId: string) => {
  approveSignal(signalId)  // 调用composable
}

// 3. 逻辑层：业务逻辑处理
const { approveSignal } = useSignalActions()
const approveSignal = async (signalId: string) => {
  await ElMessageBox.confirm('确认批准？')
  await signalStore.approveSignal(signalId)  // 调用store action
  ElMessage.success('已批准')
}

// 4. 状态管理：更新状态
const approveSignal = async (signalId: string) => {
  await signalApi.approveSignal(signalId)  // 调用API
  const signal = signals.value.find(s => s.id === signalId)
  if (signal) signal.status = 'approved'  // 更新状态
}

// 5. 数据层：发送请求
export const signalApi = {
  approveSignal(id: string) {
    return apiClient.post(`/api/signals/${id}/approve`)
  }
}

// 6. 响应式更新：Vue自动更新视图
```

## 6. 核心功能实现示例

### 6.1 K线图买卖点标注

```typescript
// components/charts/KLineChart/index.vue
<template>
  <div ref="chartRef" :style="{ height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { KLineData, TradingSignal } from '@/types/models'

interface Props {
  data: KLineData[]
  signals: TradingSignal[]
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  height: '600px'
})

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

onMounted(() => {
  initChart()
})

watch(() => [props.data, props.signals], () => {
  updateChart()
}, { deep: true })

const initChart = () => {
  if (!chartRef.value) return
  
  chart = echarts.init(chartRef.value)
  
  const option = {
    backgroundColor: '#131722',
    grid: {
      left: 60,
      right: 60,
      top: 40,
      bottom: 60
    },
    xAxis: {
      type: 'category',
      data: props.data.map(d => d.date),
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#787b86' }
    },
    yAxis: {
      type: 'value',
      position: 'right',
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#787b86' },
      splitLine: { lineStyle: { color: '#2a2e39' } }
    },
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: props.data.map(d => [d.open, d.close, d.low, d.high]),
        itemStyle: {
          color: '#26a69a',
          color0: '#ef5350',
          borderColor: '#26a69a',
          borderColor0: '#ef5350'
        }
      },
      {
        name: '买入点',
        type: 'scatter',
        data: getBuySignals(),
        symbol: 'triangle',
        symbolSize: 12,
        itemStyle: { color: '#26a69a' },
        label: {
          show: true,
          position: 'bottom',
          formatter: '买',
          color: '#26a69a'
        }
      },
      {
        name: '卖出点',
        type: 'scatter',
        data: getSellSignals(),
        symbol: 'triangle',
        symbolRotate: 180,
        symbolSize: 12,
        itemStyle: { color: '#ef5350' },
        label: {
          show: true,
          position: 'top',
          formatter: '卖',
          color: '#ef5350'
        }
      }
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(19, 23, 34, 0.9)',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc' },
      formatter: (params: any) => {
        // 自定义tooltip显示买卖点详情
        return formatTooltip(params)
      }
    }
  }
  
  chart.setOption(option)
}

const getBuySignals = () => {
  return props.signals
    .filter(s => s.type === 'buy')
    .map(s => {
      const index = props.data.findIndex(d => d.date === s.date)
      return [index, s.price, s]
    })
}

const getSellSignals = () => {
  return props.signals
    .filter(s => s.type === 'sell')
    .map(s => {
      const index = props.data.findIndex(d => d.date === s.date)
      return [index, s.price, s]
    })
}

const updateChart = () => {
  if (!chart) return
  // 更新图表数据
}
</script>
```

### 6.2 Agent工作日志实时更新

```typescript
// views/AgentWorklog/index.vue
<template>
  <div class="agent-worklog">
    <div class="timeline">
      <TimelineItem
        v-for="log in logs"
        :key="log.id"
        :log="log"
        @view-detail="viewDetail"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { useWebSocket } from '@/composables/useWebSocket'

const agentStore = useAgentStore()
const { logs } = storeToRefs(agentStore)

// WebSocket实时接收Agent日志
const { on } = useWebSocket(import.meta.env.VITE_WS_URL)

onMounted(() => {
  agentStore.fetchLogs()
  
  // 监听实时日志
  on('agent:log', (newLog) => {
    agentStore.addLog(newLog)
  })
})

const viewDetail = (logId: string) => {
  router.push({ name: 'AgentLogDetail', params: { id: logId } })
}
</script>
```

### 6.3 复现验证功能

```typescript
// views/SignalVerify/index.vue
<template>
  <div class="signal-verify">
    <div class="split-view">
      <!-- 左侧：Agent分析结果 -->
      <div class="agent-result">
        <h3>Agent分析结果</h3>
        <AnalysisSteps :steps="agentAnalysis" />
      </div>
      
      <!-- 右侧：人工复现结果 -->
      <div class="manual-result">
        <h3>人工复现结果</h3>
        <Button @click="startVerify">开始复现</Button>
        <AnalysisSteps v-if="manualAnalysis" :steps="manualAnalysis" />
      </div>
    </div>
    
    <!-- 底部：差异对比 -->
    <div class="diff-view" v-if="showDiff">
      <h3>差异分析</h3>
      <DiffTable :agent="agentAnalysis" :manual="manualAnalysis" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useSignalStore } from '@/stores/signals'
import { signalApi } from '@/services/api/signal'

const route = useRoute()
const signalId = route.params.id as string

const agentAnalysis = ref(null)
const manualAnalysis = ref(null)
const showDiff = ref(false)

onMounted(async () => {
  // 加载Agent分析结果
  const signal = await signalApi.getSignalById(signalId)
  agentAnalysis.value = signal.analysis
})

const startVerify = async () => {
  // 使用相同参数重新执行分析
  manualAnalysis.value = await signalApi.verifySignal(signalId)
  showDiff.value = true
}
</script>
```

## 7. 性能优化策略

### 7.1 组件层面

- **虚拟滚动**：长列表使用虚拟滚动（vue-virtual-scroller）
- **懒加载**：路由懒加载、组件懒加载
- **防抖节流**：搜索、滚动事件使用防抖节流
- **计算属性缓存**：充分利用computed的缓存特性

```typescript
// 虚拟滚动示例
import { RecycleScroller } from 'vue-virtual-scroller'

<RecycleScroller
  :items="signals"
  :item-size="80"
  key-field="id"
>
  <template #default="{ item }">
    <SignalCard :signal="item" />
  </template>
</RecycleScroller>
```

### 7.2 数据层面

- **请求合并**：批量请求合并为单个请求
- **数据缓存**：使用LRU缓存热点数据
- **增量更新**：WebSocket只推送变化的数据
- **分页加载**：大数据集分页加载

```typescript
// 请求缓存示例
class CachedApiClient {
  private cache = new Map<string, { data: any; timestamp: number }>()
  private cacheTTL = 60000 // 1分钟
  
  async get<T>(url: string, useCache = true): Promise<T> {
    if (useCache) {
      const cached = this.cache.get(url)
      if (cached && Date.now() - cached.timestamp < this.cacheTTL) {
        return cached.data
      }
    }
    
    const data = await apiClient.get<T>(url)
    this.cache.set(url, { data, timestamp: Date.now() })
    return data
  }
}
```

### 7.3 图表优化

- **按需渲染**：只渲染可见区域的图表
- **降采样**：大数据量时降采样显示
- **Canvas优化**：使用Canvas渲染大量数据点
- **WebWorker**：复杂计算放到WebWorker

```typescript
// 图表降采样示例
const downsample = (data: number[], targetSize: number) => {
  if (data.length <= targetSize) return data
  
  const step = Math.floor(data.length / targetSize)
  return data.filter((_, i) => i % step === 0)
}
```

## 8. 开发规范

### 8.1 命名规范

- **组件名**：PascalCase（如 `SignalCard.vue`）
- **文件名**：kebab-case（如 `use-signal-actions.ts`）
- **变量名**：camelCase（如 `currentSignal`）
- **常量名**：UPPER_SNAKE_CASE（如 `API_BASE_URL`）
- **类型名**：PascalCase（如 `TradingSignal`）

### 8.2 代码组织

```typescript
// 组件内代码顺序
<script setup lang="ts">
// 1. 导入
import { ref, computed, onMounted } from 'vue'
import { useStore } from '@/stores/xxx'

// 2. 类型定义
interface Props { }
interface Emits { }

// 3. Props和Emits
const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 4. 响应式状态
const state = ref()

// 5. 计算属性
const computed = computed(() => {})

// 6. 方法
const method = () => {}

// 7. 生命周期
onMounted(() => {})
</script>
```

### 8.3 TypeScript规范

- 所有API接口必须定义类型
- 避免使用`any`，使用`unknown`代替
- 使用类型推断，避免冗余类型标注
- 使用联合类型和类型守卫

```typescript
// 类型定义示例
export interface TradingSignal {
  id: string
  symbol: string
  type: 'buy' | 'sell'
  price: number
  confidence: number
  reasons: string[]
  status: SignalStatus
  createdAt: string
  operator: 'agent' | 'manual'
}

export type SignalStatus = 'pending' | 'approved' | 'rejected' | 'executed'

// 类型守卫
export function isBuySignal(signal: TradingSignal): signal is TradingSignal & { type: 'buy' } {
  return signal.type === 'buy'
}
```

## 9. 测试策略

### 9.1 单元测试

```typescript
// tests/unit/stores/signals.spec.ts
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useSignalStore } from '@/stores/signals'
import { signalApi } from '@/services/api/signal'

vi.mock('@/services/api/signal')

describe('Signal Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  
  it('should fetch signals', async () => {
    const mockSignals = [{ id: '1', symbol: '600519' }]
    vi.mocked(signalApi.getSignals).mockResolvedValue(mockSignals)
    
    const store = useSignalStore()
    await store.fetchSignals()
    
    expect(store.signals).toEqual(mockSignals)
  })
  
  it('should approve signal', async () => {
    const store = useSignalStore()
    store.signals = [{ id: '1', status: 'pending' }]
    
    await store.approveSignal('1')
    
    expect(store.signals[0].status).toBe('approved')
  })
})
```

### 9.2 组件测试

```typescript
// tests/unit/components/SignalCard.spec.ts
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import SignalCard from '@/components/trading/SignalCard.vue'

describe('SignalCard', () => {
  it('should render signal info', () => {
    const signal = {
      id: '1',
      symbol: '600519',
      type: 'buy',
      price: 1820,
      confidence: 85
    }
    
    const wrapper = mount(SignalCard, {
      props: { signal }
    })
    
    expect(wrapper.text()).toContain('600519')
    expect(wrapper.text()).toContain('1820')
  })
  
  it('should emit approve event', async () => {
    const wrapper = mount(SignalCard, {
      props: { signal: { id: '1' } }
    })
    
    await wrapper.find('.approve-btn').trigger('click')
    
    expect(wrapper.emitted('approve')).toBeTruthy()
    expect(wrapper.emitted('approve')[0]).toEqual(['1'])
  })
})
```

### 9.3 E2E测试

```typescript
// tests/e2e/signal-approval.spec.ts
import { test, expect } from '@playwright/test'

test('approve signal workflow', async ({ page }) => {
  await page.goto('/signals')
  
  // 等待信号列表加载
  await page.waitForSelector('.signal-card')
  
  // 点击第一个信号的批准按钮
  await page.click('.signal-card:first-child .approve-btn')
  
  // 确认对话框
  await page.click('.el-message-box__btns .el-button--primary')
  
  // 验证成功消息
  await expect(page.locator('.el-message--success')).toBeVisible()
  
  // 验证信号状态更新
  await expect(page.locator('.signal-card:first-child .status')).toHaveText('已批准')
})
```

## 10. 部署配置

### 10.1 环境变量

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_TITLE=量化交易系统（开发）

# .env.production
VITE_API_BASE_URL=https://api.quant.example.com
VITE_WS_URL=wss://api.quant.example.com
VITE_APP_TITLE=量化交易系统
```

### 10.2 构建优化

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'ui-vendor': ['element-plus'],
          'chart-vendor': ['echarts']
        }
      }
    },
    chunkSizeWarningLimit: 1000
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

## 11. 总结

### 11.1 架构优势

✅ **清晰的职责分离**：展示层、逻辑层、数据层各司其职
✅ **高可维护性**：模块化设计，易于定位和修改
✅ **可测试性强**：每层都可独立测试
✅ **可扩展性好**：新增功能只需添加对应层的代码
✅ **类型安全**：TypeScript全覆盖，减少运行时错误
✅ **性能优化**：虚拟滚动、懒加载、缓存等多种优化手段

### 11.2 下一步行动

1. **初始化项目**：使用Vite创建Vue 3 + TypeScript项目
2. **安装依赖**：安装Element Plus、ECharts、Pinia等核心依赖
3. **搭建基础架构**：创建目录结构、配置路由、配置状态管理
4. **开发核心组件**：从通用组件开始，逐步开发业务组件
5. **集成后端API**：对接quantsys CLI的API接口
6. **实现核心功能**：K线图、信号管理、Agent日志等
7. **测试与优化**：编写测试、性能优化、用户体验优化

---

**参考资源**：
- Vue 3官方文档：https://vuejs.org/
- Pinia官方文档：https://pinia.vuejs.org/
- Element Plus：https://element-plus.org/
- ECharts：https://echarts.apache.org/
- TypeScript：https://www.typescriptlang.org/

