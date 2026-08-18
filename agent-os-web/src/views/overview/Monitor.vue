<template>
  <div class="monitor">
    <el-card>
      <template #header>
        <div class="header">
          <span>实时监控</span>
          <div class="controls">
            <el-tag :type="wsConnected ? 'success' : 'danger'" size="small">
              {{ wsConnected ? '已连接' : '已断开' }}
            </el-tag>
            <el-button-group size="small" style="margin-left: 10px">
              <el-button :disabled="!wsConnected" @click="paused = !paused">
                {{ paused ? '继续' : '暂停' }}
              </el-button>
              <el-button @click="clearEvents">清空</el-button>
            </el-button-group>
          </div>
        </div>
      </template>

      <!-- 事件类型过滤 -->
      <div class="filters">
        <el-checkbox-group v-model="selectedTypes">
          <el-checkbox label="task">任务事件</el-checkbox>
          <el-checkbox label="decision">决策事件</el-checkbox>
          <el-checkbox label="memory">记忆事件</el-checkbox>
          <el-checkbox label="quota">配额事件</el-checkbox>
          <el-checkbox label="system">系统事件</el-checkbox>
        </el-checkbox-group>
      </div>

      <!-- 实时统计 -->
      <el-row :gutter="20" class="stats">
        <el-col :span="6">
          <el-statistic title="今日事件数" :value="todayEventCount" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="运行中任务" :value="runningTasks" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="排队任务" :value="queuedTasks" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="连接时长" :value="connectionDuration" suffix="秒" />
        </el-col>
      </el-row>

      <!-- 事件流 -->
      <div class="event-stream">
        <el-timeline>
          <el-timeline-item
            v-for="event in filteredEvents"
            :key="event.id"
            :timestamp="formatTime(event.timestamp)"
            :type="getEventType(event.type)"
          >
            <div class="event-content">
              <el-tag size="small" :type="getEventTagType(event.type)">
                {{ event.type }}
              </el-tag>
              <span class="event-message">{{ event.message }}</span>
              <div v-if="event.data" class="event-data">
                <el-button link size="small" @click="toggleEventDetail(event.id)">
                  {{ expandedEvents.has(event.id) ? '收起' : '详情' }}
                </el-button>
                <pre v-if="expandedEvents.has(event.id)" class="event-detail">{{
                  JSON.stringify(event.data, null, 2)
                }}</pre>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
        <div v-if="filteredEvents.length === 0" class="empty">
          <el-empty description="暂无事件" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { formatTime } from '@/utils/format'
import logger from '@/utils/logger'
import type { Event } from '@/types/api'

interface Event {
  id: string
  type: string
  message: string
  timestamp: string
  data?: any
}

const wsConnected = ref(false)
const paused = ref(false)
const events = ref<Event[]>([])
const selectedTypes = ref(['task', 'decision', 'memory', 'quota', 'system'])
const expandedEvents = ref<Set<string>>(new Set())
const runningTasks = ref(0)
const queuedTasks = ref(0)
const connectionStartTime = ref<number>(0)
const connectionDuration = ref(0)

let ws: WebSocket | null = null
let durationInterval: number | null = null

const todayEventCount = computed(() => {
  const today = new Date().toISOString().split('T')[0]
  return events.value.filter(e => e.timestamp.startsWith(today)).length
})

const filteredEvents = computed(() => {
  if (paused.value) return events.value.filter(e => selectedTypes.value.includes(e.type))
  return events.value
    .filter(e => selectedTypes.value.includes(e.type))
    .slice(-50) // 只显示最近 50 条
})

const getEventType = (type: string) => {
  const typeMap: Record<string, any> = {
    task: 'primary',
    decision: 'success',
    memory: 'info',
    quota: 'warning',
    system: 'danger',
  }
  return typeMap[type] || 'info'
}

const getEventTagType = (type: string) => {
  const typeMap: Record<string, any> = {
    task: 'primary',
    decision: 'success',
    memory: 'info',
    quota: 'warning',
    system: 'danger',
  }
  return typeMap[type] || ''
}

const toggleEventDetail = (id: string) => {
  if (expandedEvents.value.has(id)) {
    expandedEvents.value.delete(id)
  } else {
    expandedEvents.value.add(id)
  }
}

const clearEvents = () => {
  events.value = []
  expandedEvents.value.clear()
}

const connectWebSocket = () => {
  const wsUrl = 'ws://127.0.0.1:8081/ws/events'
  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    wsConnected.value = true
    connectionStartTime.value = Date.now()
    logger.log('WebSocket 已连接')
    
    // 启动连接时长计时器
    durationInterval = window.setInterval(() => {
      connectionDuration.value = Math.floor((Date.now() - connectionStartTime.value) / 1000)
    }, 1000)
  }

  ws.onmessage = (event) => {
    if (paused.value) return
    
    try {
      const data = JSON.parse(event.data)
      const newEvent: Event = {
        id: `${Date.now()}-${Math.random()}`,
        type: data.type || 'system',
        message: data.message || JSON.stringify(data),
        timestamp: new Date().toISOString(),
        data: data.data || data,
      }
      
      events.value.push(newEvent)
      
      // 更新统计
      if (data.type === 'task' && data.status === 'running') {
        runningTasks.value++
      }
      if (data.type === 'task' && data.status === 'queued') {
        queuedTasks.value++
      }
      
      // 限制事件数量
      if (events.value.length > 500) {
        events.value = events.value.slice(-500)
      }
    } catch (e) {
      logger.error('解析 WebSocket 消息失败:', e)
    }
  }

  ws.onerror = (error) => {
    logger.error('WebSocket 错误:', error)
  }

  ws.onclose = () => {
    wsConnected.value = false
    logger.log('WebSocket 已断开')
    
    if (durationInterval) {
      clearInterval(durationInterval)
      durationInterval = null
    }
    
    // 3 秒后重连
    setTimeout(() => {
      if (!wsConnected.value) {
        connectWebSocket()
      }
    }, 3000)
  }
}

onMounted(() => {
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
  if (durationInterval) {
    clearInterval(durationInterval)
  }
})
</script>

<style scoped>
.monitor {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.controls {
  display: flex;
  align-items: center;
}

.filters {
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stats {
  margin-bottom: 20px;
}

.event-stream {
  max-height: 600px;
  overflow-y: auto;
}

.event-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-message {
  margin-left: 8px;
}

.event-data {
  margin-top: 4px;
}

.event-detail {
  margin-top: 8px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
}

.empty {
  padding: 40px 0;
  text-align: center;
}
</style>
