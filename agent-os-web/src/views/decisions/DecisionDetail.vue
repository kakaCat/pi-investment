<template>
  <div class="decision-detail">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span>决策详情</span>
      </template>
    </el-page-header>

    <el-card v-loading="loading" style="margin-top: 20px">
      <template #header>
        <div class="header">
          <span>{{ decision.action }}</span>
          <el-tag :type="getStatusType(decision.status)">
            {{ decision.status }}
          </el-tag>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="决策 ID">{{ decision.id }}</el-descriptions-item>
        <el-descriptions-item label="动作">{{ decision.action }}</el-descriptions-item>
        <el-descriptions-item label="标的">{{ decision.target }}</el-descriptions-item>
        <el-descriptions-item label="置信度">
          <el-progress
            :percentage="decision.confidence * 100"
            :color="decision.confidence >= 0.8 ? '#67c23a' : decision.confidence >= 0.5 ? '#e6a23c' : '#f56c6c'"
          />
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(decision.status)">
            {{ decision.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="盈亏" v-if="decision.pnl">
          <el-text :type="decision.pnl >= 0 ? 'success' : 'danger'">
            {{ decision.pnl >= 0 ? '+' : '' }}{{ decision.pnl }}%
          </el-text>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatTime(decision.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="执行时间" v-if="decision.executed_at">
          {{ formatTime(decision.executed_at) }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- 决策理由 -->
      <el-divider content-position="left">决策理由</el-divider>
      <div class="reason-section">
        <pre>{{ decision.reason || '无' }}</pre>
      </div>

      <!-- 时间线 -->
      <el-divider content-position="left">时间线</el-divider>
      <el-timeline>
        <el-timeline-item
          v-for="event in decision.timeline"
          :key="event.timestamp"
          :timestamp="formatTime(event.timestamp)"
          :type="getTimelineType(event.type)"
        >
          {{ event.description }}
        </el-timeline-item>
      </el-timeline>

      <!-- 相关数据 -->
      <el-divider content-position="left">相关数据</el-divider>
      <div class="data-section">
        <pre>{{ JSON.stringify(decision.data, null, 2) }}</pre>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { decisionApi } from '@/api/decisions'
import { formatTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const loading = ref(false)

const decision = ref<any>({
  id: '',
  action: '',
  target: '',
  confidence: 0,
  status: '',
  reason: '',
  pnl: null,
  created_at: '',
  executed_at: '',
  timeline: [],
  data: {},
})

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    pending: 'info',
    executed: 'success',
    cancelled: 'warning',
    failed: 'danger',
  }
  return types[status] || 'info'
}

const getTimelineType = (type: string) => {
  const types: Record<string, any> = {
    created: 'primary',
    executed: 'success',
    cancelled: 'warning',
    failed: 'danger',
  }
  return types[type] || 'info'
}

const loadDecision = async () => {
  loading.value = true
  try {
    const id = route.params.id as string
    const result = await decisionApi.get(id)
    decision.value = result.decision || {}
  } catch (e) {
    console.error('加载决策详情失败:', e)
    ElMessage.error('加载决策详情失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  loadDecision()
})
</script>

<style scoped>
.decision-detail {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.reason-section,
.data-section {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.reason-section pre,
.data-section pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
