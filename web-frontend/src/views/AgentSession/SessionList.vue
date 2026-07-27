<template>
  <div class="session-list-page">
    <el-card>
      <template #header>
        <div class="header-row">
          <span class="title">Agent 会话</span>
          <div class="actions">
            <el-select v-model="channelFilter" placeholder="全部通道" clearable style="width: 140px" @change="loadSessions">
              <el-option label="全部" value="" />
              <el-option label="Wake" value="wake" />
              <el-option label="飞书" value="feishu" />
              <el-option label="CLI" value="cli" />
            </el-select>
            <el-button :loading="loading" @click="loadSessions">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="sessions" v-loading="loading" @row-click="goDetail" style="cursor: pointer">
        <el-table-column label="会话" min-width="280">
          <template #default="{ row }">
            <span :title="row.session_key">{{ shortenKey(row.session_key) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="通道" width="100">
          <template #default="{ row }">
            <el-tag :type="channelTagType(row.channel)" size="small">{{ channelLabel(row.channel) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message_count" label="消息" width="80" align="center" />
        <el-table-column prop="tool_call_count" label="工具" width="80" align="center" />
        <el-table-column label="错误" width="80" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.error_count > 0 ? '#f56c6c' : 'inherit', fontWeight: row.error_count > 0 ? 600 : 400 }">
              {{ row.error_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最后活跃" width="160">
          <template #default="{ row }">{{ formatTime(row.last_active_at) }}</template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && sessions.length === 0" description="暂无会话记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { agentSessionApi } from '@/services/api/agentSession'
import { usePolling } from '@/composables/usePolling'
import type { AgentSession } from '@/types'

const router = useRouter()
const sessions = ref<AgentSession[]>([])
const loading = ref(false)
const channelFilter = ref('')

async function loadSessions() {
  loading.value = true
  try {
    const params: { channel?: string; limit: number } = { limit: 50 }
    if (channelFilter.value) params.channel = channelFilter.value
    const data = await agentSessionApi.list(params)
    sessions.value = data.sessions
  } finally {
    loading.value = false
  }
}

usePolling(loadSessions, 30000)

function goDetail(row: AgentSession) {
  router.push(`/agent-session/${encodeURIComponent(row.session_key)}`)
}

function shortenKey(key: string): string {
  return key.length > 40 ? key.slice(0, 24) + '…' + key.slice(-12) : key
}

const channelLabel = (c: string) => ({ wake: 'Wake', feishu: '飞书', cli: 'CLI' }[c] ?? c)
const channelTagType = (c: string) => (({ wake: 'primary', feishu: 'success', cli: 'info' } as Record<string, any>)[c] ?? 'info')

function formatTime(iso: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  const diffMin = Math.floor((Date.now() - d.getTime()) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} 小时前`
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 600; }
.actions { display: flex; gap: 8px; }
</style>
