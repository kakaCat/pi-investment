<template>
  <div class="pipeline-page">
    <!-- 一键运行配置 -->
    <el-card shadow="never" class="mb-4">
      <h3 class="text-base font-semibold mb-4">一键量化链路</h3>
      <div class="grid grid-cols-4 gap-4 mb-4">
        <el-form-item label="股票范围" label-width="80px">
          <el-input
            v-model="config.stockRange"
            placeholder="如 600519.SH,000858.SZ 或留空=全部"
          />
        </el-form-item>

        <el-form-item label="数据天数" label-width="80px">
          <el-input-number
            v-model="config.days"
            :min="30"
            :max="1000"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="模型" label-width="80px">
          <el-select v-model="config.model" style="width: 100%">
            <el-option label="XGBoost" value="xgboost" />
            <el-option label="LightGBM" value="lightgbm" />
            <el-option label="RandomForest" value="randomforest" />
          </el-select>
        </el-form-item>

        <el-form-item label="信号阈值" label-width="80px">
          <el-input-number
            v-model="config.threshold"
            :min="0.5"
            :max="0.95"
            :step="0.05"
            style="width: 100%"
          />
        </el-form-item>
      </div>

      <el-button
        type="primary"
        size="large"
        :loading="running"
        @click="runPipeline"
      >
        <el-icon class="mr-1"><VideoPlay /></el-icon>
        一键运行全链路
      </el-button>
    </el-card>

    <!-- 链路阶段可视化 -->
    <el-card shadow="never" class="mb-4">
      <h3 class="text-base font-semibold mb-4">链路阶段</h3>

      <div class="flex items-center gap-2 mb-6">
        <!-- Stage 1: 数据更新 -->
        <div
          class="flex-1 rounded-lg p-4 text-center"
          :class="getStageClass(stages[0])"
        >
          <div class="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2" :class="getStageIconClass(stages[0])">
            <el-icon :size="20"><DataLine /></el-icon>
          </div>
          <div class="text-sm font-medium">1. 数据更新</div>
          <div class="text-xs mt-1">{{ getStageStatus(stages[0]) }}</div>
          <div class="text-xs text-gray-400 mt-1">{{ stages[0].detail }}</div>
        </div>

        <div class="text-gray-300 text-lg">→</div>

        <!-- Stage 2: 因子计算 -->
        <div
          class="flex-1 rounded-lg p-4 text-center"
          :class="getStageClass(stages[1])"
        >
          <div class="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2" :class="getStageIconClass(stages[1])">
            <el-icon :size="20"><Operation /></el-icon>
          </div>
          <div class="text-sm font-medium">2. 因子计算</div>
          <div class="text-xs mt-1">{{ getStageStatus(stages[1]) }}</div>
          <div class="text-xs text-gray-400 mt-1">{{ stages[1].detail }}</div>
        </div>

        <div class="text-gray-300 text-lg">→</div>

        <!-- Stage 3: ML预测 -->
        <div
          class="flex-1 rounded-lg p-4 text-center"
          :class="getStageClass(stages[2])"
        >
          <div class="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2" :class="getStageIconClass(stages[2])">
            <el-icon :size="20"><Cpu /></el-icon>
          </div>
          <div class="text-sm font-medium">3. ML预测</div>
          <div class="text-xs mt-1">{{ getStageStatus(stages[2]) }}</div>
          <div class="text-xs text-gray-400 mt-1">{{ stages[2].detail }}</div>
        </div>

        <div class="text-gray-300 text-lg">→</div>

        <!-- Stage 4: 回测验证 -->
        <div
          class="flex-1 rounded-lg p-4 text-center"
          :class="getStageClass(stages[3])"
        >
          <div class="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2" :class="getStageIconClass(stages[3])">
            <el-icon :size="20"><TrendCharts /></el-icon>
          </div>
          <div class="text-sm font-medium">4. 回测验证</div>
          <div class="text-xs mt-1">{{ getStageStatus(stages[3]) }}</div>
          <div class="text-xs text-gray-400 mt-1">{{ stages[3].detail }}</div>
        </div>

        <div class="text-gray-300 text-lg">→</div>

        <!-- Stage 5: 风险评估 -->
        <div
          class="flex-1 rounded-lg p-4 text-center"
          :class="getStageClass(stages[4])"
        >
          <div class="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2" :class="getStageIconClass(stages[4])">
            <el-icon :size="20"><Lock /></el-icon>
          </div>
          <div class="text-sm font-medium">5. 风险评估</div>
          <div class="text-xs mt-1">{{ getStageStatus(stages[4]) }}</div>
          <div class="text-xs text-gray-400 mt-1">{{ stages[4].detail }}</div>
        </div>
      </div>

      <!-- 进度条 -->
      <el-progress :percentage="overallProgress" :stroke-width="8" />
      <div class="text-xs text-gray-400 mt-2 text-right">{{ overallProgress }}% 完成</div>
    </el-card>

    <!-- 历史运行记录 -->
    <el-card shadow="never">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-base font-semibold">历史运行记录</h3>
        <el-button :icon="Refresh" @click="fetchHistory">刷新</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="history"
        stripe
      >
        <el-table-column prop="runId" label="运行ID" width="120">
          <template #default="{ row }">
            <span class="font-mono text-xs text-gray-500">{{ row.runId }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="startTime" label="时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.startTime) }}
          </template>
        </el-table-column>

        <el-table-column prop="stockCount" label="股票数" width="100" align="right" />

        <el-table-column prop="model" label="模型" width="120" />

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'"
              size="small"
            >
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="signalCount" label="信号数" width="100" align="right">
          <template #default="{ row }">
            {{ row.signalCount || '-' }}
          </template>
        </el-table-column>

        <el-table-column prop="bestReturn" label="最佳回测" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.bestReturn" :class="row.bestReturn >= 0 ? 'text-red-500' : 'text-green-600'" class="font-medium">
              {{ formatPercent(row.bestReturn) }}
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="riskLevel" label="风险等级" width="100">
          <template #default="{ row }">
            <el-tag
              v-if="row.riskLevel"
              :type="row.riskLevel === 'low' ? 'success' : row.riskLevel === 'medium' ? 'warning' : 'danger'"
              size="small"
            >
              {{ getRiskLevelText(row.riskLevel) }}
            </el-tag>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="duration" label="耗时" width="100">
          <template #default="{ row }">
            {{ formatDuration(row.duration) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewLogs(row)">查看日志</el-button>
            <el-button v-if="row.status === 'failed'" type="primary" link @click="retryRun(row)">重试</el-button>
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
          @current-change="fetchHistory"
        />
      </div>
    </el-card>

    <!-- 日志对话框 -->
    <el-dialog
      v-model="logDialogVisible"
      title="运行日志"
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
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, Operation, Cpu, TrendCharts, Refresh, DataLine, Lock } from '@element-plus/icons-vue'
import { formatDateTime, formatPercent } from '@/utils/format'
import { usePolling } from '@/composables/usePolling'
import { pipelineApi, type PipelineRun, type StageStatus } from '@/services/api/pipeline'

type Stage = StageStatus

// 配置
const config = reactive({
  stockRange: '',
  days: 365,
  model: 'xgboost',
  threshold: 0.65
})

// 状态
const running = ref(false)
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 阶段状态
const stages = reactive<Stage[]>([
  { name: '数据更新', status: 'pending', progress: 0, detail: '' },
  { name: '因子计算', status: 'pending', progress: 0, detail: '' },
  { name: 'ML预测', status: 'pending', progress: 0, detail: '' },
  { name: '回测验证', status: 'pending', progress: 0, detail: '' },
  { name: '风险评估', status: 'pending', progress: 0, detail: '' }
])

// 历史记录
const history = ref<PipelineRun[]>([])

// 日志
const logDialogVisible = ref(false)
const logs = ref<string[]>([])

// 总进度
const overallProgress = computed(() => {
  const total = stages.reduce((sum, stage) => sum + stage.progress, 0)
  return Math.round(total / stages.length)
})

// 运行流水线
const runPipeline = async () => {
  running.value = true

  // 重置阶段状态
  stages.forEach(stage => {
    stage.status = 'pending'
    stage.progress = 0
    stage.detail = ''
  })

  try {
    const result = await pipelineApi.runPipeline(config)
    ElMessage.success(`流水线已启动: ${result.runId}`)

    // 开始轮询获取进度
    pollRunStatus(result.runId)
  } catch (error) {
    ElMessage.error('流水线启动失败')
    console.error('Pipeline run error:', error)
    running.value = false
  }
}

// 轮询运行状态
const pollRunStatus = async (runId: string) => {
  const maxAttempts = 120 // 最多轮询2分钟
  let attempts = 0

  const poll = async () => {
    try {
      const run = await pipelineApi.getRun(runId)

      // 更新阶段状态
      if (run.stages && Array.isArray(run.stages)) {
        stages.forEach((stage, index) => {
          if (run.stages[index]) {
            Object.assign(stage, run.stages[index])
          }
        })
      }

      // 检查是否完成
      if (run.status === 'completed' || run.status === 'failed') {
        running.value = false
        if (run.status === 'completed') {
          ElMessage.success('流水线运行完成')
        } else {
          ElMessage.error('流水线运行失败' + (run.error ? ': ' + run.error : ''))
        }
        fetchHistory()
        return
      }

      // 继续轮询
      attempts++
      if (attempts < maxAttempts) {
        setTimeout(poll, 1000)
      } else {
        running.value = false
        ElMessage.warning('轮询超时，请刷新查看状态')
        fetchHistory()
      }
    } catch (error) {
      // 降级：如果 getRun 失败，尝试从响应中推断运行仍在进行
      if (attempts < 5) {
        // 前几次尝试中，后端可能尚未写入记录，继续轮询
        attempts++
        setTimeout(poll, 2000)
      } else {
        console.error('Poll error:', error)
        running.value = false
        ElMessage.warning('获取运行状态失败，请手动刷新')
        fetchHistory()
      }
    }
  }

  poll()
}

// 获取阶段样式
const getStageClass = (stage: Stage) => {
  if (stage.status === 'completed') return 'bg-green-50 border border-green-200'
  if (stage.status === 'running') return 'bg-blue-50 border border-blue-200 ring-2 ring-blue-300'
  if (stage.status === 'failed') return 'bg-red-50 border border-red-200'
  return 'bg-gray-50 border border-gray-200'
}

const getStageIconClass = (stage: Stage) => {
  if (stage.status === 'completed') return 'bg-green-100 text-green-600'
  if (stage.status === 'running') return 'bg-blue-100 text-blue-600'
  if (stage.status === 'failed') return 'bg-red-100 text-red-600'
  return 'bg-gray-100 text-gray-400'
}

const getStageStatus = (stage: Stage) => {
  if (stage.status === 'completed') return '✓ 完成'
  if (stage.status === 'running') return `⟳ 运行中... ${stage.progress}%`
  if (stage.status === 'failed') return '✗ 失败'
  return '等待中'
}

// 获取历史记录
const fetchHistory = async () => {
  loading.value = true
  try {
    const response = await pipelineApi.getHistory(currentPage.value, pageSize.value)
    history.value = response.items
    total.value = response.pagination.total
  } catch (error) {
    ElMessage.error('获取历史记录失败')
    console.error('Fetch history error:', error)
  } finally {
    loading.value = false
  }
}

// 查看日志
const viewLogs = async (run: PipelineRun) => {
  // 后端无专用日志端点，直接使用 run 对象中的 logs
  if (run.logs && run.logs.length > 0) {
    logs.value = run.logs
    logDialogVisible.value = true
  } else {
    // 尝试从 runs/list 获取最新日志（降级方案）
    try {
      const fetchedRun = await pipelineApi.getRun(run.runId)
      if (fetchedRun.logs && fetchedRun.logs.length > 0) {
        logs.value = fetchedRun.logs
        logDialogVisible.value = true
      } else {
        ElMessage.warning('暂无日志数据')
      }
    } catch {
      ElMessage.warning('暂无日志数据')
    }
  }
}

// 重试运行
const retryRun = (run: PipelineRun) => {
  ElMessage.info(`重试运行 ${run.runId}`)
  runPipeline()
}

// 格式化耗时
const formatDuration = (seconds: number) => {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${s}s`
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

// 获取风险等级文本
const getRiskLevelText = (level: string) => {
  const map: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险'
  }
  return map[level] || level
}

// 自动刷新
const { start: startPolling, stop: stopPolling } = usePolling(fetchHistory, 30000)

onMounted(() => {
  fetchHistory()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.pipeline-page {
  padding: 20px;
}
</style>
