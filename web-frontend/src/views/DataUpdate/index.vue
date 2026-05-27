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
              v-if="row.status === 'running' || row.status === 'queued'"
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
              v-if="row.status === 'running' || row.status === 'queued'"
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
import { dataApi } from '@/services/api'

interface UpdateJob {
  jobId: string
  source: string
  days: number
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled'
  total: number | null
  success: number
  failed: number
  progress: number
  createdAt: string
  completedAt: string | null
  type?: string
  params?: any
  result?: any
  error?: string
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
    const response = await dataApi.getJobs({
      page: currentPage.value,
      pageSize: pageSize.value
    })

    // response 现在是 PaginatedResponse<DataUpdateJob> 格式
    // items 已由 data.ts 中的 mapJobToDataUpdateJob 转换为标准格式
    jobs.value = response.items.map(job => ({
      jobId: job.jobId,
      source: job.source,
      days: job.days,
      status: job.status,
      total: job.total || null,
      success: job.success,
      failed: job.failed,
      progress: job.progress,
      createdAt: job.createdAt,
      completedAt: job.completedAt || null,
      type: job.type,
      params: job.params,
      result: job.result,
      error: job.error
    }))

    total.value = response.total
  } catch (error) {
    console.error('获取任务列表失败:', error)
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

// 开始更新
const startUpdate = async () => {
  updating.value = true
  try {
    const result = await dataApi.startUpdate({
      scope: updateConfig.source as 'hs300' | 'watchlist' | 'portfolio' | 'all',
      days: updateConfig.days,
      forceUpdate: updateConfig.force
    })

    ElMessage.success(`数据更新任务已创建: ${result.jobId}`)

    // 刷新任务列表
    await fetchJobs()
  } catch (error: any) {
    console.error('启动数据更新失败:', error)
    ElMessage.error(error?.message || '启动数据更新失败')
  } finally {
    updating.value = false
  }
}

// 停止任务
const stopJob = async (job: UpdateJob) => {
  try {
    await dataApi.cancelJob(job.jobId)
    ElMessage.success('任务已取消')
    await fetchJobs()
  } catch (error: any) {
    console.error('停止任务失败:', error)
    ElMessage.error(error?.message || '停止任务失败')
  }
}

// 重试任务
const retryJob = async (job: UpdateJob) => {
  try {
    await dataApi.retryJob(job.jobId)
    ElMessage.success('任务已重新提交')
    await fetchJobs()
  } catch (error: any) {
    console.error('重试任务失败:', error)
    ElMessage.error(error?.message || '重试任务失败')
  }
}

// 查看日志
const viewLogs = (job: UpdateJob) => {
  const logLines: string[] = []

  logLines.push(`[${job.createdAt}] 任务开始: ${job.jobId}`)
  logLines.push(`[${job.createdAt}] 数据源: ${job.source}, 天数: ${job.days}`)

  if (job.params) {
    logLines.push(`[${job.createdAt}] 参数: ${JSON.stringify(job.params, null, 2)}`)
  }

  if (job.result) {
    logLines.push(`[${job.createdAt}] 结果: 总数 ${job.total || 0}, 成功 ${job.success}, 失败 ${job.failed}`)
  }

  if (job.error) {
    logLines.push(`[${job.completedAt || job.createdAt}] 错误: ${job.error}`)
  }

  if (job.status === 'success') {
    logLines.push(`[${job.completedAt}] 任务完成: 成功 ${job.success}, 失败 ${job.failed}`)
  } else if (job.status === 'failed') {
    logLines.push(`[${job.completedAt}] 任务失败: 成功 ${job.success}, 失败 ${job.failed}`)
  } else if (job.status === 'running') {
    logLines.push(`[${new Date().toISOString()}] 运行中: 成功 ${job.success}, 失败 ${job.failed}, 进度 ${job.progress}%`)
  }

  logs.value = logLines
  logDialogVisible.value = true
}

// 获取状态类型
const getStatusType = (status: string) => {
  const map: Record<string, any> = {
    queued: 'info',
    pending: 'info',
    running: 'primary',
    success: 'success',
    completed: 'success',
    failed: 'danger',
    cancelled: 'warning'
  }
  return map[status] || 'info'
}

// 获取状态文本
const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    queued: '排队中',
    pending: '排队中',
    running: '运行中',
    success: '完成',
    completed: '完成',
    failed: '失败',
    cancelled: '已取消'
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
