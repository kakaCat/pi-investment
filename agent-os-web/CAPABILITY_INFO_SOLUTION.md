# Registry 能力信息获取方案

## 🔍 问题分析

**问题**: Registry 页面要显示"能力详细说明"，但 Agent OS 只存储能力 ID

**当前存储**:
```json
{
  "capabilities": [
    "kline-data",
    "backtesting",
    "signal-generation"
  ]
}
```

**想要展示**:
```
• kline-data - K线数据查询
  API: GET /api/kline
  说明: 提供股票历史和实时K线数据

• backtesting - 策略回测
  API: POST /api/backtest
  说明: 执行策略回测，返回收益率和风险指标
```

---

## 🎯 解决方案（3种）

### 方案 1: 前端硬编码映射（推荐 MVP）⭐⭐⭐

**原理**: 在前端代码中维护一个能力字典

**实现**:
```typescript
// src/utils/capabilities.ts

export interface CapabilityInfo {
  id: string
  name: string
  icon: string
  description: string
  category: string
  apiPath?: string
}

export const CAPABILITY_MAP: Record<string, CapabilityInfo> = {
  'kline-data': {
    id: 'kline-data',
    name: 'K线数据',
    icon: '📊',
    description: '提供股票历史和实时K线数据查询',
    category: 'data',
    apiPath: 'GET /api/kline'
  },
  
  'market-analysis': {
    id: 'market-analysis',
    name: '市场分析',
    icon: '🔍',
    description: '技术面和基本面分析，市场趋势判断',
    category: 'analysis',
    apiPath: 'GET /api/analysis'
  },
  
  'signal-generation': {
    id: 'signal-generation',
    name: '信号生成',
    icon: '📈',
    description: '基于策略生成买入/卖出信号',
    category: 'trading',
    apiPath: 'POST /api/signals/generate'
  },
  
  'backtesting': {
    id: 'backtesting',
    name: '策略回测',
    icon: '🔬',
    description: '执行策略回测，返回收益率和风险指标',
    category: 'analysis',
    apiPath: 'POST /api/backtest'
  },
  
  'portfolio-management': {
    id: 'portfolio-management',
    name: '组合管理',
    icon: '💼',
    description: '持仓组合优化和调整建议',
    category: 'trading',
    apiPath: 'GET /api/portfolio'
  },
  
  'risk-management': {
    id: 'risk-management',
    name: '风险管理',
    icon: '⚠️',
    description: '风险评估、止损止盈建议',
    category: 'trading',
    apiPath: 'GET /api/risk'
  },
  
  'trading-execution': {
    id: 'trading-execution',
    name: '交易执行',
    icon: '⚡',
    description: '执行买入/卖出交易指令',
    category: 'trading',
    apiPath: 'POST /api/trades'
  },
  
  // 未来 agent-dh 的能力
  'decision-making': {
    id: 'decision-making',
    name: '决策制定',
    icon: '🧠',
    description: 'AI 决策引擎，综合分析后做出投资决策',
    category: 'ai'
  },
  
  'learning': {
    id: 'learning',
    name: '学习优化',
    icon: '📚',
    description: '从历史数据中学习，优化策略参数',
    category: 'ai'
  },
  
  'orchestration': {
    id: 'orchestration',
    name: '任务编排',
    icon: '🎯',
    description: '协调多个服务完成复杂任务',
    category: 'ai'
  }
}

// 工具函数
export function getCapabilityInfo(id: string): CapabilityInfo {
  return CAPABILITY_MAP[id] || {
    id,
    name: id,
    icon: '❓',
    description: '未知能力',
    category: 'unknown'
  }
}

export function getCapabilityIcon(id: string): string {
  return getCapabilityInfo(id).icon
}

export function getCapabilityName(id: string): string {
  return getCapabilityInfo(id).name
}
```

**使用**:
```vue
<template>
  <div v-for="cap in agent.capabilities" :key="cap">
    {{ getCapabilityIcon(cap) }} {{ getCapabilityName(cap) }}
  </div>
  
  <!-- 详情弹窗 -->
  <div v-for="cap in agent.capabilities" :key="cap">
    <h4>{{ getCapabilityIcon(cap) }} {{ getCapabilityInfo(cap).name }}</h4>
    <p>{{ getCapabilityInfo(cap).description }}</p>
    <code>{{ getCapabilityInfo(cap).apiPath }}</code>
  </div>
</template>

<script setup lang="ts">
import { getCapabilityInfo, getCapabilityIcon, getCapabilityName } from '@/utils/capabilities'
</script>
```

**优点**:
- ✅ 简单快速，1小时完成
- ✅ 不需要修改后端
- ✅ 前端完全控制展示内容

**缺点**:
- ❌ 能力变化时需要改前端代码
- ❌ 不同服务无法自定义说明

**适用场景**: MVP 阶段，能力相对固定

---

### 方案 2: 元数据扩展（推荐正式版）⭐⭐⭐⭐

**原理**: 在注册时通过 metadata 传递能力详细信息

**quantsys-v2 注册时**:
```python
payload = {
    "agent_id": self.agent_id,
    "type": "trading-system",
    "capabilities": [
        "kline-data",
        "backtesting",
        "signal-generation"
    ],
    "metadata": {
        "service": "quantsys-v2",
        "description": "量化交易系统后端",
        "api_base": "http://127.0.0.1:5001",
        
        # 新增：能力详细信息
        "capability_details": {
            "kline-data": {
                "name": "K线数据查询",
                "description": "提供股票历史和实时K线数据",
                "api_path": "GET /api/kline",
                "doc_url": "http://127.0.0.1:5001/docs#kline"
            },
            "backtesting": {
                "name": "策略回测",
                "description": "执行策略回测，返回收益率和风险指标",
                "api_path": "POST /api/backtest",
                "parameters": ["strategy_id", "start_date", "end_date"],
                "doc_url": "http://127.0.0.1:5001/docs#backtest"
            },
            "signal-generation": {
                "name": "信号生成",
                "description": "基于策略生成买入/卖出信号",
                "api_path": "POST /api/signals/generate",
                "doc_url": "http://127.0.0.1:5001/docs#signals"
            }
        }
    }
}
```

**Agent OS 存储**:
- capabilities 字段：存储能力 ID 列表（用于搜索）
- metadata 字段：存储完整的能力详情（JSONB）

**前端获取**:
```typescript
// API 返回
{
  "agent_id": "quantsys-v2-12345",
  "capabilities": ["kline-data", "backtesting", "signal-generation"],
  "metadata": {
    "capability_details": {
      "kline-data": {
        "name": "K线数据查询",
        "description": "...",
        "api_path": "GET /api/kline"
      }
    }
  }
}

// 前端使用
const capDetails = agent.metadata.capability_details
const klineInfo = capDetails['kline-data']
console.log(klineInfo.name) // "K线数据查询"
```

**优点**:
- ✅ 每个服务可以自定义能力说明
- ✅ 不需要改数据库结构
- ✅ 支持动态扩展
- ✅ 信息准确（由服务自己提供）

**缺点**:
- ⚠️ 需要修改注册代码
- ⚠️ 如果服务不提供详情，前端需要回退到方案1

**适用场景**: 正式版本，多个服务

---

### 方案 3: 独立能力服务（不推荐）

**原理**: 创建一个能力信息服务，提供能力字典

**实现**:
```
GET /api/v1/capabilities
→ 返回所有已知能力的详细信息

GET /api/v1/capabilities/kline-data
→ 返回单个能力的详细信息
```

**优点**:
- ✅ 统一管理能力信息
- ✅ 前后端解耦

**缺点**:
- ❌ 过度设计，增加复杂度
- ❌ 需要额外维护能力字典
- ❌ 多一次 API 调用

**适用场景**: 大型系统，能力非常多且频繁变化

---

## ✅ 推荐实施方案

### 第一阶段（MVP - 现在）：方案 1 ⭐⭐⭐

**实现步骤**（1小时）:

1. 创建 `src/utils/capabilities.ts`
   - 定义能力字典
   - 图标、名称、描述

2. 在 Registry 页面使用
   - 显示能力图标和名称
   - 详情弹窗显示完整信息

**交付**:
- ✅ 立即可用
- ✅ 显示效果完整
- ✅ 不依赖后端改动

### 第二阶段（正式版 - 未来）：方案 2 ⭐⭐⭐⭐

**实现步骤**（2-3小时）:

1. 修改 quantsys-v2 注册代码
   - 在 metadata 中添加 capability_details

2. 修改前端逻辑
   - 优先使用 metadata 中的详情
   - 如果没有，回退到方案1的字典

**交付**:
- ✅ 支持服务自定义能力说明
- ✅ 向后兼容
- ✅ 信息更准确

---

## 📋 具体实现示例

### 前端组件代码

```vue
<!-- AgentCard.vue -->
<template>
  <el-card class="agent-card">
    <div class="agent-header">
      <el-badge :value="statusText" :type="statusType">
        <h3>{{ agent.agent_id }}</h3>
      </el-badge>
      <span class="heartbeat">💓 {{ heartbeatText }}</span>
    </div>
    
    <div class="agent-info">
      <p>{{ agent.agent_type }} · {{ uptimeText }}</p>
      <p>{{ apiBase }}</p>
    </div>
    
    <div class="capabilities">
      <el-tag
        v-for="cap in agent.capabilities"
        :key="cap"
        class="capability-tag"
      >
        <span class="icon">{{ getCapabilityIcon(cap) }}</span>
        <span>{{ getCapabilityName(cap) }}</span>
      </el-tag>
    </div>
    
    <div class="actions">
      <el-button size="small" @click="showDetail">查看详情</el-button>
      <el-button size="small" @click="openApiDocs">API 文档</el-button>
    </div>
  </el-card>
  
  <!-- 详情弹窗 -->
  <el-dialog v-model="detailVisible" title="服务详情" width="600px">
    <el-descriptions :column="2" border>
      <el-descriptions-item label="Agent ID">{{ agent.agent_id }}</el-descriptions-item>
      <el-descriptions-item label="类型">{{ agent.agent_type }}</el-descriptions-item>
      <el-descriptions-item label="状态">{{ agent.status }}</el-descriptions-item>
      <el-descriptions-item label="版本">{{ agent.version }}</el-descriptions-item>
      <el-descriptions-item label="进程 ID">{{ agent.pid }}</el-descriptions-item>
      <el-descriptions-item label="注册时间">{{ formatTime(agent.registered_at) }}</el-descriptions-item>
    </el-descriptions>
    
    <h4 style="margin-top: 20px">能力详情</h4>
    <div v-for="cap in agent.capabilities" :key="cap" class="capability-detail">
      <h5>
        <span class="icon">{{ getCapabilityIcon(cap) }}</span>
        {{ getCapabilityInfo(cap).name }}
      </h5>
      <p>{{ getCapabilityInfo(cap).description }}</p>
      <el-tag v-if="getCapabilityInfo(cap).apiPath" type="info" size="small">
        {{ getCapabilityInfo(cap).apiPath }}
      </el-tag>
    </div>
    
    <h4 style="margin-top: 20px">心跳历史</h4>
    <el-timeline>
      <el-timeline-item
        v-for="(beat, index) in heartbeatHistory"
        :key="index"
        :timestamp="beat.time"
        :type="beat.success ? 'success' : 'danger'"
      >
        {{ beat.success ? '正常' : '失败' }}
      </el-timeline-item>
    </el-timeline>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { getCapabilityInfo, getCapabilityIcon, getCapabilityName } from '@/utils/capabilities'
import type { Agent } from '@/types/registry'

const props = defineProps<{
  agent: Agent
}>()

const detailVisible = ref(false)

const statusType = computed(() => {
  const now = Date.now()
  const lastBeat = new Date(props.agent.last_heartbeat_at).getTime()
  const diff = (now - lastBeat) / 1000 // 秒
  
  if (diff < 60) return 'success'    // 1分钟内 - 正常
  if (diff < 120) return 'warning'   // 2分钟内 - 警告
  return 'danger'                     // 超过2分钟 - 异常
})

const statusText = computed(() => {
  const type = statusType.value
  return type === 'success' ? '在线' : type === 'warning' ? '异常' : '离线'
})

const heartbeatText = computed(() => {
  const now = Date.now()
  const lastBeat = new Date(props.agent.last_heartbeat_at).getTime()
  const diff = Math.floor((now - lastBeat) / 1000)
  
  if (diff < 60) return `${diff}秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  return `${Math.floor(diff / 3600)}小时前`
})

const uptimeText = computed(() => {
  const now = Date.now()
  const registered = new Date(props.agent.registered_at).getTime()
  const diff = Math.floor((now - registered) / 1000)
  
  const hours = Math.floor(diff / 3600)
  const minutes = Math.floor((diff % 3600) / 60)
  
  return `运行 ${hours}小时${minutes}分钟`
})

const apiBase = computed(() => {
  return props.agent.metadata?.api_base || `http://${props.agent.host}:${props.agent.port}`
})

function showDetail() {
  detailVisible.value = true
}

function openApiDocs() {
  const docsUrl = props.agent.metadata?.docs || `${apiBase.value}/docs`
  window.open(docsUrl, '_blank')
}
</script>

<style scoped>
.agent-card {
  margin-bottom: 16px;
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.heartbeat {
  font-size: 14px;
  color: #909399;
}

.agent-info {
  margin-bottom: 12px;
  font-size: 14px;
  color: #606266;
}

.capabilities {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.capability-tag {
  display: flex;
  align-items: center;
  gap: 4px;
}

.capability-tag .icon {
  font-size: 16px;
}

.capability-detail {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 12px;
}

.capability-detail h5 {
  margin: 0 0 8px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.capability-detail .icon {
  font-size: 20px;
}

.capability-detail p {
  margin: 0 0 8px 0;
  color: #606266;
}
</style>
```

---

## 📊 总结

### 当前推荐：方案 1（前端硬编码）

**立即实现**（1小时）:
1. 创建 `capabilities.ts` 能力字典
2. 在 Registry 页面使用

**优点**:
- ✅ 快速（1小时）
- ✅ 不依赖后端
- ✅ 效果完整

### 未来升级：方案 2（元数据扩展）

**后续优化**（2-3小时）:
1. 修改 quantsys-v2 注册代码
2. 前端支持动态能力详情

**优点**:
- ✅ 更灵活
- ✅ 信息更准确
- ✅ 向后兼容

---

**文档创建时间**: 2024-08-19  
**版本**: 1.0
