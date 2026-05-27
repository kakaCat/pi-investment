<template>
  <div class="scheduler-page">
    <!-- 提示横幅 -->
    <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-sm text-amber-700">
      <span class="font-medium">提示：</span>定时任务已接入后端调度系统，配置持久化在服务端。按 Cron 表达式自动执行，也可手动触发。
    </div>

    <!-- 顶部操作栏 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-5 mb-4">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-slate-800">定时任务</h2>
        <button class="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600" @click="showAddDialog">+ 新建任务</button>
      </div>
    </div>

    <!-- 任务卡片网格 -->
    <div class="grid grid-cols-2 gap-4 mb-4">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="bg-white rounded-xl shadow-sm border border-slate-200 p-5"
      >
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span
              class="w-2 h-2 rounded-full"
              :class="task.enabled ? 'bg-green-500' : 'bg-slate-400'"
            />
            <h3 class="font-semibold text-slate-800">{{ task.name }}</h3>
          </div>
          <span class="text-xs px-2 py-0.5 rounded-full" :class="task.enabled ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'">
            {{ task.enabled ? '已启用' : '已暂停' }}
          </span>
        </div>

        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span class="text-xs text-slate-400">Cron</span>
            <div class="font-mono text-sm">{{ task.cron }}</div>
          </div>
          <div>
            <span class="text-xs text-slate-400">命令</span>
            <div class="text-sm">{{ task.command }}</div>
          </div>
          <div>
            <span class="text-xs text-slate-400">参数</span>
            <div class="text-sm text-slate-600">{{ task.params || '-' }}</div>
          </div>
          <div>
            <span class="text-xs text-slate-400">上次运行</span>
            <div class="text-sm">
              {{ task.lastRun ? formatDateTime(task.lastRun) : '-' }}
              <span v-if="task.lastStatus" :class="task.lastStatus === 'success' ? 'text-green-600' : 'text-red-500'" class="text-xs">
                {{ task.lastStatus === 'success' ? '✓' : '✗' }}
              </span>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100">
          <button class="text-xs px-3 py-1 border border-slate-200 rounded hover:bg-slate-50" @click="task.enabled ? triggerTask(task) : toggleTask(task)">
            {{ task.enabled ? '立即触发' : '启用' }}
          </button>
          <button class="text-xs px-3 py-1 border border-slate-200 rounded hover:bg-slate-50" @click="task.enabled ? toggleTask(task) : triggerTask(task)">
            {{ task.enabled ? '暂停' : '立即触发' }}
          </button>
          <button class="text-xs px-3 py-1 border border-slate-200 rounded hover:bg-slate-50 text-red-500" @click="deleteTask(task)">删除</button>
        </div>
      </div>
    </div>

    <!-- 运行历史 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div class="p-4 bg-slate-50 border-b border-slate-200">
        <h3 class="font-semibold text-slate-800">运行历史</h3>
      </div>
      <table class="w-full">
        <thead>
          <tr class="bg-slate-50">
            <th>任务</th><th>状态</th><th>开始时间</th><th>完成时间</th><th>耗时</th><th>结果</th><th>错误</th>
          </tr>
        </thead>
        <tbody class="text-sm">
          <tr v-for="row in history" :key="row.id">
            <td class="font-medium">{{ row.taskName }}</td>
            <td>
              <span class="text-xs px-2 py-0.5 rounded-full" :class="row.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
                {{ row.status === 'success' ? '成功' : '失败' }}
              </span>
            </td>
            <td>{{ formatTime(row.startTime) }}</td>
            <td>{{ formatTime(row.endTime) }}</td>
            <td>{{ formatDuration(row.duration) }}</td>
            <td class="text-xs">{{ row.result || '-' }}</td>
            <td>
              <span v-if="row.error" class="text-xs text-red-500">{{ row.error }}</span>
              <span v-else>-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新建/编辑任务对话框 -->
    <el-dialog
      v-model="taskDialogVisible"
      :title="isEdit ? '编辑任务' : '新建任务'"
      width="600px"
    >
      <el-form :model="taskForm" label-width="100px">
        <el-form-item label="任务名称">
          <el-input v-model="taskForm.name" placeholder="例如: 数据更新" />
        </el-form-item>

        <el-form-item label="任务类型">
          <el-select v-model="taskForm.command" placeholder="选择任务类型" style="width: 100%">
            <el-option label="数据更新" value="data_update" />
            <el-option label="信号生成" value="signal_generate" />
            <el-option label="风控检查" value="risk_check" />
            <el-option label="日报生成" value="report_daily" />
            <el-option label="策略回测" value="strategy_backtest" />
            <el-option label="模型训练" value="model_train" />
          </el-select>
        </el-form-item>

        <el-form-item label="Cron表达式">
          <el-input
            v-model="taskForm.cron"
            placeholder="例如: 0 8 * * 1-5 (工作日早上8点)"
          >
            <template #append>
              <el-button @click="showCronHelper">帮助</el-button>
            </template>
          </el-input>
          <div class="text-xs text-gray-400 mt-1">
            下次执行: {{ getNextRunTime(taskForm.cron || '') }}
          </div>
        </el-form-item>

        <el-form-item label="任务参数">
          <el-input
            v-model="taskForm.params"
            type="textarea"
            :rows="3"
            placeholder="例如: source: hs300, days: 730"
          />
        </el-form-item>

        <el-form-item label="任务描述">
          <el-input
            v-model="taskForm.description"
            type="textarea"
            :rows="2"
            placeholder="任务说明"
          />
        </el-form-item>

        <el-form-item label="是否启用">
          <el-switch v-model="taskForm.enabled" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTask">保存</el-button>
      </template>
    </el-dialog>

    <!-- 日志对话框 -->
    <el-dialog
      v-model="logDialogVisible"
      title="执行日志"
      width="800px"
    >
      <div class="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm h-96 overflow-y-auto">
        <div v-for="(log, index) in logs" :key="index" class="mb-1">
          {{ log }}
        </div>
      </div>
    </el-dialog>

    <!-- Cron帮助对话框 -->
    <el-dialog
      v-model="cronHelpVisible"
      title="Cron表达式帮助"
      width="600px"
    >
      <div class="text-sm">
        <p class="mb-2">Cron表达式格式: <code class="bg-gray-100 px-2 py-1 rounded">分 时 日 月 周</code></p>
        <el-divider />
        <h4 class="font-semibold mb-2">常用示例:</h4>
        <ul class="space-y-2">
          <li><code class="bg-gray-100 px-2 py-1 rounded">0 8 * * 1-5</code> - 工作日早上8点</li>
          <li><code class="bg-gray-100 px-2 py-1 rounded">30 9 * * *</code> - 每天早上9点30分</li>
          <li><code class="bg-gray-100 px-2 py-1 rounded">*/30 * * * *</code> - 每30分钟</li>
          <li><code class="bg-gray-100 px-2 py-1 rounded">0 */2 * * *</code> - 每2小时</li>
          <li><code class="bg-gray-100 px-2 py-1 rounded">0 0 * * 0</code> - 每周日午夜</li>
          <li><code class="bg-gray-100 px-2 py-1 rounded">0 15 * * 1-5</code> - 工作日下午3点</li>
        </ul>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime, formatTime } from '@/utils/format'
import { apiClient } from '@/services/api/client'

interface Task {
  id: string
  name: string
  command: string
  cron: string
  params: string
  description: string
  enabled: boolean
  lastRun: string | null
  lastStatus: 'success' | 'failed' | null
}

interface HistoryRecord {
  id: string
  taskName: string
  status: 'success' | 'failed'
  startTime: string
  endTime: string
  duration: number
  result: string
  error: string
}

// ── Backend ↔ Frontend mappers ────────────────────────────────────────

/** Map backend SchedulerTaskSummary → frontend Task */
const mapTask = (t: Record<string, unknown>): Task => {
  const payload = (t.payload ?? {}) as Record<string, unknown>
  const lastRun = t.lastRun as Record<string, unknown> | undefined
  const lastStatus = lastRun
    ? (lastRun.status === 'success' || lastRun.status === 'compensated') ? 'success' as const
    : (lastRun.status === 'failed' || lastRun.status === 'compensation_failed') ? 'failed' as const
    : null
    : null

  return {
    id: t.id as string,
    name: t.name as string,
    command: payload.command as string || '',
    cron: t.scheduleKind === 'cron' ? (t.scheduleExpr as string || '') : '',
    params: formatPayloadParams(payload),
    description: payload.description as string || '',
    enabled: Boolean(t.enabled),
    lastRun: (lastRun?.finishedAt ?? lastRun?.startedAt ?? lastRun?.triggeredAt ?? null) as string | null,
    lastStatus,
  }
}

/** Format payload into key:value string for display (exclude command/description) */
const formatPayloadParams = (payload: Record<string, unknown>): string => {
  const { command, description, ...rest } = payload
  const entries = Object.entries(rest)
  if (entries.length === 0) return ''
  return entries.map(([k, v]) => `${k}: ${v}`).join(', ')
}

/** Map backend SchedulerRun → frontend HistoryRecord */
const mapRun = (r: Record<string, unknown>): HistoryRecord => ({
  id: r.id as string,
  taskName: r.taskName as string,
  status: (r.status === 'success' || r.status === 'compensated') ? 'success' : 'failed',
  startTime: (r.startedAt ?? r.triggeredAt ?? '') as string,
  endTime: (r.finishedAt ?? '') as string,
  duration: typeof r.durationMs === 'number' ? Math.round(r.durationMs / 1000) : 0,
  result: typeof r.payload === 'object' ? JSON.stringify(r.payload) : String(r.payload ?? ''),
  error: (r.error ?? '') as string,
})

/** Build backend payload object from task form data */
const buildPayload = (form: Record<string, unknown>): Record<string, unknown> => {
  const payload: Record<string, unknown> = {}
  if (form.command) payload.command = form.command
  if (form.description) payload.description = form.description

  const paramsStr = String(form.params ?? '').trim()
  if (paramsStr) {
    try {
      const parsed = JSON.parse(paramsStr)
      if (typeof parsed === 'object' && parsed !== null) {
        Object.assign(payload, parsed)
      } else {
        payload.params = form.params
      }
    } catch {
      const pairs: Record<string, string> = {}
      paramsStr.split(',').forEach((pair) => {
        const colonIdx = pair.indexOf(':')
        if (colonIdx > 0) {
          pairs[pair.slice(0, colonIdx).trim()] = pair.slice(colonIdx + 1).trim()
        }
      })
      if (Object.keys(pairs).length > 0) {
        Object.assign(payload, pairs)
      } else {
        payload.params = form.params
      }
    }
  }
  return payload
}

// ── State ──────────────────────────────────────────────────────────────

const loading = ref(false)
const tasks = ref<Task[]>([])

// 加载任务列表
const loadTasks = async () => {
  loading.value = true
  try {
    const result = await apiClient.get('/api/scheduler/tasks')
    const list = (result as any).tasks || []
    tasks.value = list.map(mapTask)
  } catch (error) {
    console.error('加载调度任务失败:', error)
    ElMessage.error('加载调度任务失败')
  } finally {
    loading.value = false
  }
}

// 历史记录
const history = ref<HistoryRecord[]>([])

// 加载执行历史
const loadHistory = async () => {
  try {
    const result = await apiClient.get('/api/scheduler/runs', { params: { limit: 50 } })
    const runs = (result as any).runs || []
    history.value = runs.map(mapRun)
  } catch (error) {
    console.error('加载执行历史失败:', error)
  }
}

// 对话框
const taskDialogVisible = ref(false)
const logDialogVisible = ref(false)
const cronHelpVisible = ref(false)
const isEdit = ref(false)

// 表单
const taskForm = reactive<Partial<Task>>({
  name: '',
  command: '',
  cron: '',
  params: '',
  description: '',
  enabled: true,
})

// 日志
const logs = ref<string[]>([])

// 显示新建对话框
const showAddDialog = () => {
  isEdit.value = false
  Object.assign(taskForm, {
    name: '',
    command: '',
    cron: '',
    params: '',
    description: '',
    enabled: true,
  })
  taskDialogVisible.value = true
}

// 保存任务（创建 / 更新）
const saveTask = async () => {
  if (!taskForm.name || !taskForm.command || !taskForm.cron) {
    ElMessage.warning('请填写完整信息')
    return
  }

  const body = {
    name: taskForm.name,
    enabled: taskForm.enabled !== false,
    scheduleKind: 'cron' as const,
    scheduleExpr: taskForm.cron,
    payload: buildPayload(taskForm as Record<string, unknown>),
  }

  try {
    if (isEdit.value && taskForm.id) {
      await apiClient.put(`/api/scheduler/tasks/${taskForm.id}`, body)
      ElMessage.success('任务已更新')
    } else {
      await apiClient.post('/api/scheduler/tasks', body)
      ElMessage.success('任务已创建')
    }
    taskDialogVisible.value = false
    await loadTasks()
  } catch (error: any) {
    const msg = error?.message || '保存失败'
    ElMessage.error(msg)
  }
}

// 触发任务
const triggerTask = async (task: Task) => {
  try {
    await apiClient.post(`/api/scheduler/tasks/${task.id}/trigger`)
    ElMessage.success(`任务 ${task.name} 已触发`)
    await loadTasks()
  } catch (error: any) {
    ElMessage.error(error?.message || '触发失败')
  }
}

// 切换任务启用/暂停状态
const toggleTask = async (task: Task) => {
  const action = task.enabled ? 'disable' : 'enable'
  try {
    await apiClient.post(`/api/scheduler/tasks/${task.id}/${action}`)
    ElMessage.success(`任务已${task.enabled ? '暂停' : '启用'}`)
    await loadTasks()
  } catch (error: any) {
    ElMessage.error(error?.message || '操作失败')
  }
}

// 删除任务
const deleteTask = (task: Task) => {
  ElMessageBox.confirm(`确定要删除任务 ${task.name} 吗？`, '确认删除', {
    type: 'warning',
  }).then(async () => {
    try {
      await apiClient.delete(`/api/scheduler/tasks/${task.id}`)
      ElMessage.success('任务已删除')
      await loadTasks()
    } catch (error: any) {
      ElMessage.error(error?.message || '删除失败')
    }
  }).catch(() => {})
}

// 显示Cron帮助
const showCronHelper = () => {
  cronHelpVisible.value = true
}

// 获取下次运行时间
const getNextRunTime = (_cron: string) => {
  if (!_cron) return '-'
  return '2026-05-22 08:00:00'
}

// 格式化耗时
const formatDuration = (seconds: number) => {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${s}s`
}

onMounted(() => {
  loadTasks()
  loadHistory()
})
</script>

<style scoped>
.scheduler-page {
  color: #1e293b;
  padding: 0;
}

.scheduler-page button {
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

code {
  font-family: 'Courier New', monospace;
}

table {
  border-collapse: collapse;
  font-size: 13px;
}

th {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  padding: 12px 16px;
  text-align: left;
}

td {
  border-top: 1px solid #f1f5f9;
  color: #334155;
  padding: 12px 16px;
}

@media (max-width: 900px) {
  .grid.grid-cols-2 {
    grid-template-columns: minmax(0, 1fr);
  }

  .scheduler-page {
    overflow-x: auto;
  }
}
</style>
