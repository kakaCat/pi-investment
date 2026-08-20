<template>
  <div class="monitor">
    <el-card>
      <template #header>
        <div class="header">
          <span>实时事件流</span>
          <div class="controls">
            <el-tag :type="connected ? 'success' : 'danger'">
              {{ connected ? '🟢 已连接' : '🔴 已断开' }}
            </el-tag>
            <el-button :type="paused ? 'success' : 'warning'" size="small" @click="togglePause">
              {{ paused ? '继续' : '暂停' }}
            </el-button>
            <el-button type="danger" size="small" @click="clearEvents">清空</el-button>
          </div>
        </div>
      </template>

      <!-- 过滤器 -->
      <div class="filters">
        <el-checkbox-group v-model="filters">
          <el-checkbox label="task">任务事件</el-checkbox>
          <el-checkbox label="decision">决策事件</el-checkbox>
          <el-checkbox label="memory">记忆事件</el-checkbox>
          <el-checkbox label="quota">配额事件</el-checkbox>
        </el-checkbox-group>
      </div>

      <!-- 事件列表 -->
      <div class="event-list">
        <div
          v-for="(event, index) in filteredEvents"
          :key="index"
          class="event-item"
          :style="{ borderLeftColor: getEventColor(event.type) }"
        >
          <div class="event-header">
            <el-tag size="small" :style="{ backgroundColor: getEventColor(event.type) }">
              {{ event.type }}
            </el-tag>
            <span class="time">{{ timeAgo(event.timestamp) }}</span>
          </div>
          <div class="event-content">
            <span class="agent-id">Agent: {{ event.agent_id }}</span>
            <pre class="data">{{ JSON.stringify(event.data, null, 2) }}</pre>
          </div>
        </div>
        <div v-if="filteredEvents.length === 0" class="empty">
          <el-empty description="暂无事件" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { EventItem } from '@/types'
import { timeAgo } from '@/utils/format'

const events = ref<EventItem[]>([])
const connected = ref(false)
const paused = ref(false)
const filters = ref(['task', 'decision', 'memory', 'quota'])
let ws: WebSocket | null = null

const eventColors: Record<string, string> = {
  'task.started': '#409eff',
  'task.completed': '#67c23a',
  'task.failed': '#f56c6c',
  'decision.recorded': '#e6a23c',
  'memory.created': '#909399',
  'quota.warning': '#f56c6c',
}

const getEventColor = (type: string): string => {
  return eventColors[type] || '#909399'
}

const filteredEvents = computed(() => {
  return events.value.filter((event) => {
    const category = event.type.split('.')[0]
    return filters.value.includes(category)
  })
})

const togglePause = () => {
  paused.value = !paused.value
}

const clearEvents = () => {
  events.value = []
}

onMounted(() => {
  connectWebSocket()
})

const connectWebSocket = () => {
  try {
    ws = new WebSocket('ws://127.0.0.1:8081/ws/events')

    ws.onopen = () => {
      connected.value = true
      console.log('[Monitor] WebSocket 连接成功')
    }

    ws.onmessage = (e) => {
      if (!paused.value) {
        try {
          const event = JSON.parse(e.data)
          // 忽略连接建立等系统消息
          if (event.type === 'connected') return
          events.value.unshift({
            type: event.type || 'system',
            agent_id: event.agent_id || '-',
            data: event.data || {},
            timestamp: event.timestamp || new Date().toISOString(),
          })
          if (events.value.length > 100) {
            events.value.pop()
          }
        } catch (err) {
          console.error('[Monitor] 解析事件失败:', err)
        }
      }
    }

    ws.onclose = () => {
      connected.value = false
      console.log('[Monitor] WebSocket 连接关闭，3秒后重连...')
      setTimeout(connectWebSocket, 3000)
    }

    ws.onerror = (err) => {
      console.error('[Monitor] WebSocket 错误:', err)
      connected.value = false
    }
  } catch (err) {
    console.error('[Monitor] WebSocket 连接失败:', err)
    connected.value = false
    // 3秒后重试
    setTimeout(connectWebSocket, 3000)
  }
}

onUnmounted(() => {
  if (ws) {
    ws.onclose = null // 移除重连逻辑
    ws.close()
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
  gap: 10px;
  align-items: center;
}
.filters {
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}
.event-list {
  max-height: 600px;
  overflow-y: auto;
}
.event-item {
  padding: 12px;
  margin-bottom: 8px;
  border-left: 4px solid;
  background: #fafafa;
  border-radius: 4px;
}
.event-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.time {
  color: #909399;
  font-size: 12px;
}
.event-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.agent-id {
  color: #606266;
  font-size: 14px;
}
.data {
  background: #fff;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #303133;
  overflow-x: auto;
}
.empty {
  padding: 40px 0;
}
</style>
