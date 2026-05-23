<template>
  <div class="data-update-page">
    <!-- 更新配置 -->
    <el-card shadow="never" class="mb-4">
      <h2 class="text-base font-semibold mb-4">数据更新</h2>

      <div class="flex items-center gap-3">
        <el-select
          v-model="updateConfig.source"
          placeholder="选择数据源"
          style="width: 200px"
        >
          <el-option label="沪深300 (hs300)" value="hs300" />
          <el-option label="自选股 (watchlist)" value="watchlist" />
          <el-option label="持仓 (portfolio)" value="portfolio" />
          <el-option label="全部 (all)" value="all" />
        </el-select>

        <el-input-number
          v-model="updateConfig.days"
          :min="1"
          :max="3650"
          style="width: 150px"
        />
        <span class="text-xs text-gray-400">天</span>

        <el-checkbox v-model="updateConfig.force" class="ml-2">
          强制更新
        </el-checkbox>

        <el-button
          type="primary"
          :loading="updating"
          :icon="VideoPlay"
          class="ml-auto"
          @click="startUpdate"
        >
          开始更新
        </el-button>
      </div>
    </el-card>

    <!-- 更新任务记录 -->
    <el-card shadow="never">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-base font-semibold">更新任务记录</h3>
        <el-button :icon="Refresh" @click="fetchJobs">刷新</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="jobs"
        stripe
      >
        <el-table-column prop="jobId" label="Job ID" width="180">
          <template #default="{ row }">
            <span class="text-gray-400 font-mono text-xs">{{ row.jobId }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="source" label="数据源" width="120" />

        <el-table-column prop="days" label="天数" width="80" align="right" />

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="getStatusType(row.status)"
              size="small"
            >
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="total" label="总数" width="80" align="right">
          <template #default="{ row }">
            {{ row.total || '-' }}
          </template>
        </el-table-column>

        <el-table-column prop="success" label="成功" width="80" align="right">
          <template #default="{ row }">
            {{ row.success }}
          </template>
        </el-table-column>

        <el-table-column prop="failed" label="失败" width="80" align="right">
          <template #default="{ row }">
            <span :class="row.failed > 0 ? 'text-red-500' : ''">
              {{ row.failed }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <el-progress
              v-if="row.status === 'running'"
              :percentage="row.progress"
              :stroke-width="6"
            />
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="createdAt" label="创建时间" width="180">
          <template #default="{ row }">
            <span class="text-gray-500">{{ formatDateTime(row.createdAt) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="completedAt" label="完成时间" width="180">
          <template #default="{ row }">
            <span v-if="row.completedAt" class="text-gray-500">
              {{ formatDateTime(row.completedAt) }}
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'running'"
              type="danger"
              link
              @click="stopJob(row)"
            >
              停止
            </el-button>
            <el-button
              v-if="row.status === 'failed'"
              type="primary"
              link
              @click="retryJob(row)"
            >
              重试
            </el-button>
            <el-button type="primary" link @click="viewLogs(row)">
              查看日志
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="mt-4 flex justify-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchJobs"
        />
      </div>
    </el-card>

    <!-- 日志对话框 -->
    <el-dialog
      v-model="logDialogVisible"
      title="更新日志"
      width="800px"
    >
      <div class="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm h-96 overflow-y-auto">
        <div v-for="(log, index) in logs" :key="index" class="mb-1">
          {{ log }}
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, Refresh } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/format'
import { usePolling } from '@/composables/usePolling'

interface UpdateJob {
  jobId: string
  source: string
  days: number
  status: 'running' | 'completed' | 'failed'
  total: number | null
  success: number
  failed: number
  progress: number
  createdAt: string
  completedAt: string | null
}

// 状态
const loading = ref(false)
const updating = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 更新配置
const updateConfig = reactive({
  source: 'hs300',
  days: 730,
  force: false
})

// 任务列表
const jobs = ref<UpdateJob[]>([])

// 日志
const logDialogVisible = ref(false)
const logs = ref<string[]>([])

// 获取任务列表
const fetchJobs = async () => {
  loading.value = true
  try {
    // Mock数据
    jobs.value = [
      {
        jobId: 'j-20260521-001',
        source: 'hs300',
        days: 730,
        status: 'completed',
        total: 300,
        success: 300,
        failed: 0,
        progress: 100,
        createdAt: '2026-05-21 09:00:00',
        completedAt: '2026-05-21 09:12:00'
      },
      {
        jobId: 'j-20260520-003',
        source: 'portfolio',
        days: 365,
        status: 'completed',
        total: 8,
        success: 8,
        failed: 0,
        progress: 100,
        createdAt: '2026-05-20 18:00:00',
        completedAt: '2026-05-20 18:03:00'
      },
      {
        jobId: 'j-20260520-002',
        source: 'watchlist',
        days: 180,
        status: 'failed',
        total: 25,
        success: 22,
        failed: 3,
        progress: 88,
        createdAt: '2026-05-20 14:00:00',
        completedAt: '2026-05-20 14:05:00'
      },
      {
        jobId: 'j-20260520-001',
        source: 'all',
        days: 730,
        status: 'running',
        total: null,
        success: 215,
        failed: 2,
        progress: 65,
        createdAt: '2026-05-20 08:00:00',
        completedAt: null
      }
    ]
    total.value = 42
  } catch (error) {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

// 开始更新
const startUpdate = async () => {
  updating.value = true
  try {
    // 模拟创建更新任务
    await new Promise(resolve => setTimeout(resolve, 1000))

    const newJob: UpdateJob = {
      jobId: `j-${new Date().toISOString().split('T')[0].replace(/-/g, '')}-${String(jobs.value.length + 1).padStart(3, '0')}`,
      source: updateConfig.source,
      days: updateConfig.days,
      status: 'running',
      total: null,
      success: 0,
      failed: 0,
      progress: 0,
      createdAt: new Date().toISOString().replace('T', ' ').split('.')[0],
      completedAt: null
    }

    jobs.value.unshift(newJob)
    ElMessage.success('更新任务已创建')
  } catch (error) {
    ElMessage.error('创建更新任务失败')
  } finally {
    updating.value = false
  }
}

// 停止任务
const stopJob = (job: UpdateJob) => {
  ElMessage.info(`停止任务 ${job.jobId}`)
  job.status = 'failed'
}

// 重试任务
const retryJob = (job: UpdateJob) => {
  ElMessage.info(`重试任务 ${job.jobId}`)
  job.status = 'running'
  job.progress = 0
  job.success = 0
  job.failed = 0
}

// 查看日志
const viewLogs = (job: UpdateJob) => {
  logs.value = [
    `[${job.createdAt}] 任务开始: ${job.jobId}`,
    `[${job.createdAt}] 数据源: ${job.source}, 天数: ${job.days}`,
    `[${job.createdAt}] 开始获取股票列表...`,
    `[${job.createdAt}] 找到 ${job.total || 300} 只股票`,
    `[${job.createdAt}] 开始下载K线数据...`,
    job.status === 'completed'
      ? `[${job.completedAt}] 任务完成: 成功 ${job.success}, 失败 ${job.failed}`
      : job.status === 'failed'
      ? `[${job.completedAt}] 任务失败: 成功 ${job.success}, 失败 ${job.failed}`
      : `[${new Date().toISOString().replace('T', ' ').split('.')[0]}] 运行中: 成功 ${job.success}, 失败 ${job.failed}, 进度 ${job.progress}%`
  ]
  logDialogVisible.value = true
}

// 获取状态类型
const getStatusType = (status: string) => {
  const map: Record<string, any> = {
    running: 'primary',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

// 获取状态文本
const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    running: '运行中',
    completed: '完成',
    failed: '失败'
  }
  return map[status] || status
}

// 自动刷新
const { start: startPolling, stop: stopPolling } = usePolling(fetchJobs, 10000)

onMounted(() => {
  fetchJobs()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.data-update-page {
  padding: 20px;
}
</style>
