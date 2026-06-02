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
      <div class="grid grid-cols-4 gap-3 text-sm mb-4">
        <div class="scheduler-stat">
          <span>总任务</span>
          <strong>{{ taskTotal }}</strong>
        </div>
        <div class="scheduler-stat">
          <span>本页启用</span>
          <strong>{{ taskStats.enabled }}</strong>
        </div>
        <div class="scheduler-stat">
          <span>本页暂停</span>
          <strong>{{ taskStats.paused }}</strong>
        </div>
        <div class="scheduler-stat">
          <span>本页异常</span>
          <strong>{{ taskStats.problem }}</strong>
        </div>
      </div>
      <div class="level-strip">
        <div
          v-for="item in taskLevelStats"
          :key="item.level"
          class="level-pill"
          :class="getTaskLevelBorderClass(item.level)"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.count }}</strong>
        </div>
      </div>
    </div>

    <!-- 任务卡片网格 -->
    <div class="task-level-list mb-4">
      <section v-for="group in taskLevelGroups" :key="group.level" class="task-level-section">
        <div class="task-level-heading">
          <span :class="getTaskLevelDotClass(group.level)" />
          <strong>{{ group.label }}</strong>
          <span>{{ group.tasks.length }}</span>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div
            v-for="task in group.tasks"
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
              <span class="text-xs px-2 py-0.5 rounded-full" :class="getTaskLevelClass(task.level)">
                {{ getTaskLevelText(task.level) }}
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
                  <span v-if="task.lastStatus" :class="getRunLevelTextClass(task.lastStatus)" class="text-xs">
                    {{ getRunLevelMark(task.lastStatus) }}
                  </span>
                </div>
              </div>
              <div>
                <span class="text-xs text-slate-400">下次执行</span>
                <div class="text-sm">{{ task.nextRun ? formatDateTime(task.nextRun) : '-' }}</div>
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
      </section>
    </div>

    <div class="mb-4 flex justify-end">
      <el-pagination
        v-model:current-page="taskPage"
        v-model:page-size="taskPageSize"
        :total="taskTotal"
        :page-sizes="[6, 12, 24, 48]"
        layout="total, sizes, prev, pager, next"
        @size-change="handleTaskPageSizeChange"
        @current-change="loadTasks"
      />
    </div>

    <!-- 运行历史 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div class="p-4 bg-slate-50 border-b border-slate-200">
        <div class="flex items-center justify-between">
          <h3 class="font-semibold text-slate-800">运行历史</h3>
          <div class="history-levels">
            <span v-for="item in historyLevelStats" :key="item.level" :class="getRunLevelClass(item.level)">
              {{ item.label }} {{ item.count }}
            </span>
          </div>
        </div>
      </div>
      <table class="w-full scheduler-history-table">
        <thead>
          <tr class="bg-slate-50">
            <th>任务</th><th>状态</th><th>开始时间</th><th>完成时间</th><th>耗时</th><th>结果</th><th>错误</th>
          </tr>
        </thead>
        <tbody class="text-sm">
          <tr v-for="row in history" :key="row.id" :class="getRunRowClass(row.status)">
            <td class="font-medium">{{ row.taskName }}</td>
            <td>
              <span class="text-xs px-2 py-0.5 rounded-full" :class="getRunLevelClass(row.status)">
                {{ getRunLevelText(row.status) }}
              </span>
            </td>
            <td>{{ formatTime(row.startTime) }}</td>
            <td>{{ formatTime(row.endTime) }}</td>
            <td>{{ formatDuration(row.duration) }}</td>
            <td class="text-xs result-cell" :title="row.resultDetail">{{ row.result || '-' }}</td>
            <td>
              <span v-if="row.error" class="text-xs text-red-500">{{ row.error }}</span>
              <span v-else>-</span>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="p-4 flex justify-end border-t border-slate-100">
        <el-pagination
          v-model:current-page="historyPage"
          v-model:page-size="historyPageSize"
          :total="historyTotal"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="handleHistoryPageSizeChange"
          @current-change="loadHistory"
        />
      </div>
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
import { ref, reactive, computed, onMounted } from 'vue'
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
  nextRun: string | null
  lastStatus: RunLevel | null
  level: TaskLevel
}

type TaskLevel = 'healthy' | 'warning' | 'failed' | 'paused' | 'idle'
type RunLevel = 'success' | 'failed' | 'internal_failed' | 'skipped'

const taskLevelOrder: TaskLevel[] = ['failed', 'warning', 'paused', 'idle', 'healthy']
const historyLevelOrder: RunLevel[] = ['failed', 'internal_failed', 'skipped', 'success']

interface HistoryRecord {
  id: string
  taskName: string
  status: RunLevel
  startTime: string
  endTime: string
  duration: number
  result: string
  resultDetail: string
  error: string
}

// ── Backend ↔ Frontend mappers ────────────────────────────────────────

/** Map backend SchedulerTaskSummary → frontend Task */
const mapTask = (t: Record<string, unknown>): Task => {
  const payload = (t.payload ?? {}) as Record<string, unknown>
  const lastRun = t.lastRun as Record<string, unknown> | undefined
  const lastStatus = lastRun ? getRunLevel(lastRun) : null
  const enabled = Boolean(t.enabled)

  return {
    id: t.id as string,
    name: t.name as string,
    command: payload.command as string || '',
    cron: t.scheduleKind === 'cron' ? (t.scheduleExpr as string || '') : '',
    params: formatPayloadParams(payload),
    description: payload.description as string || '',
    enabled,
    lastRun: (lastRun?.finishedAt ?? lastRun?.startedAt ?? lastRun?.triggeredAt ?? null) as string | null,
    nextRun: (t.nextRunAt ?? null) as string | null,
    lastStatus,
    level: getTaskLevel(enabled, lastStatus),
  }
}

/** Format payload into key:value string for display (exclude command/description) */
const formatPayloadParams = (payload: Record<string, unknown>): string => {
  const { command, description, ...rest } = payload
  const entries = Object.entries(rest)
  if (entries.length === 0) return ''
  return entries.map(([k, v]) => `${k}: ${v}`).join(', ')
}

const isDeletedTaskSummary = (t: Record<string, unknown>): boolean => {
  const payload = (t.payload ?? {}) as Record<string, unknown>
  return Boolean(payload._deleted_at || t.deletedAt || t.deleted_at)
}

const getRunLevel = (r: Record<string, unknown>): RunLevel => {
  const payload = (r.payload ?? {}) as Record<string, unknown>
  if (r.status === 'failed' || r.status === 'compensation_failed') return 'failed'
  if (r.status === 'skipped' || payload.status === 'skipped') return 'skipped'
  if (payload.status === 'failed' || payload.status === 'error') return 'internal_failed'
  return 'success'
}

const getTaskLevel = (enabled: boolean, lastStatus: RunLevel | null): TaskLevel => {
  if (!enabled) return 'paused'
  if (!lastStatus) return 'idle'
  if (lastStatus === 'failed') return 'failed'
  if (lastStatus === 'internal_failed' || lastStatus === 'skipped') return 'warning'
  return 'healthy'
}

const summarizePayload = (payload: unknown): { summary: string; detail: string } => {
  if (!payload) return { summary: '', detail: '' }
  if (typeof payload !== 'object') {
    const value = String(payload)
    return { summary: value, detail: value }
  }

  const record = payload as Record<string, unknown>
  const detail = JSON.stringify(record)
  const parts = [
    record.action ? String(record.action) : '',
    record.status ? `status=${record.status}` : '',
    typeof record.errors === 'number' ? `errors=${record.errors}` : '',
    Array.isArray(record.errors) ? `errors=${record.errors.length}` : '',
    typeof record.symbols_checked === 'number' ? `checked=${record.symbols_checked}` : '',
    typeof record.symbols_updated === 'number' ? `updated=${record.symbols_updated}` : '',
    typeof record.symbols_processed === 'number' ? `processed=${record.symbols_processed}` : '',
    typeof record.symbols_computed === 'number' ? `computed=${record.symbols_computed}` : '',
  ].filter(Boolean)

  return {
    summary: parts.join(', ') || detail,
    detail,
  }
}

/** Map backend SchedulerRun → frontend HistoryRecord */
const mapRun = (r: Record<string, unknown>): HistoryRecord => {
  const payload = summarizePayload(r.payload)
  return {
    id: String(r.id ?? ''),
    taskName: r.taskName as string,
    status: getRunLevel(r),
    startTime: (r.startedAt ?? r.triggeredAt ?? '') as string,
    endTime: (r.finishedAt ?? '') as string,
    duration: typeof r.durationMs === 'number' ? Math.round(r.durationMs / 1000) : 0,
    result: payload.summary,
    resultDetail: payload.detail,
    error: (r.error ?? '') as string,
  }
}

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
const taskPage = ref(1)
const taskPageSize = ref(12)
const taskTotal = ref(0)
const taskStats = reactive({
  enabled: 0,
  paused: 0,
  problem: 0,
})

const taskLevelStats = computed(() => taskLevelOrder.map(level => ({
  level,
  label: getTaskLevelText(level),
  count: tasks.value.filter(task => task.level === level).length,
})))

const taskLevelGroups = computed(() => taskLevelStats.value
  .map(group => ({
    ...group,
    tasks: tasks.value.filter(task => task.level === group.level),
  }))
  .filter(group => group.tasks.length > 0))

const getResponsePageItems = <T,>(items: T[], page: number, pageSize: number, hasServerPagination: boolean): T[] => {
  if (hasServerPagination) return items
  const start = (page - 1) * pageSize
  return items.slice(start, start + pageSize)
}

// 加载任务列表
const loadTasks = async () => {
  loading.value = true
  try {
    const result = await apiClient.get('/api/scheduler/tasks', {
      params: {
        page: taskPage.value,
        pageSize: taskPageSize.value,
      },
    })
    const list = (((result as any).tasks || []) as Record<string, unknown>[]).filter(item => !isDeletedTaskSummary(item))
    const pagination = (result as any).pagination || {}
    const hasServerPagination = Boolean((result as any).pagination || (result as any).total !== undefined || (result as any).count !== undefined)
    const pageItems = getResponsePageItems(list, taskPage.value, taskPageSize.value, hasServerPagination)
    tasks.value = pageItems.map(mapTask)
    taskTotal.value = hasServerPagination
      ? Number((result as any).total ?? (result as any).count ?? pagination.total ?? list.length)
      : list.length
    taskStats.enabled = tasks.value.filter(task => task.enabled).length
    taskStats.paused = tasks.value.filter(task => !task.enabled).length
    taskStats.problem = tasks.value.filter(task => task.level === 'failed' || task.level === 'warning').length
  } catch (error) {
    console.error('加载调度任务失败:', error)
    ElMessage.error('加载调度任务失败')
  } finally {
    loading.value = false
  }
}

// 历史记录
const history = ref<HistoryRecord[]>([])
const historyPage = ref(1)
const historyPageSize = ref(20)
const historyTotal = ref(0)

const historyLevelStats = computed(() => historyLevelOrder.map(level => ({
  level,
  label: getRunLevelText(level),
  count: history.value.filter(row => row.status === level).length,
})))

// 加载执行历史
const loadHistory = async () => {
  try {
    const result = await apiClient.get('/api/scheduler/runs', {
      params: {
        page: historyPage.value,
        pageSize: historyPageSize.value,
      },
    })
    const runs = (((result as any).runs || []) as Record<string, unknown>[])
    const pagination = (result as any).pagination || {}
    const hasServerPagination = Boolean((result as any).pagination || (result as any).total !== undefined || (result as any).count !== undefined)
    const pageItems = getResponsePageItems(runs, historyPage.value, historyPageSize.value, hasServerPagination)
    history.value = pageItems.map(mapRun)
    historyTotal.value = Number((result as any).total ?? (result as any).count ?? pagination.total ?? runs.length)
  } catch (error) {
    console.error('加载执行历史失败:', error)
  }
}

const handleTaskPageSizeChange = () => {
  taskPage.value = 1
  loadTasks()
}

const handleHistoryPageSizeChange = () => {
  historyPage.value = 1
  loadHistory()
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

// 格式化耗时
const formatDuration = (seconds: number) => {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${s}s`
}

const getTaskLevelText = (level: TaskLevel) => ({
  healthy: '正常',
  warning: '需关注',
  failed: '失败',
  paused: '已暂停',
  idle: '待运行',
}[level])

const getTaskLevelClass = (level: TaskLevel) => ({
  healthy: 'bg-green-100 text-green-700',
  warning: 'bg-amber-100 text-amber-700',
  failed: 'bg-red-100 text-red-700',
  paused: 'bg-slate-100 text-slate-500',
  idle: 'bg-blue-100 text-blue-700',
}[level])

const getTaskLevelBorderClass = (level: TaskLevel) => ({
  healthy: 'level-healthy',
  warning: 'level-warning',
  failed: 'level-failed',
  paused: 'level-paused',
  idle: 'level-idle',
}[level])

const getTaskLevelDotClass = (level: TaskLevel) => ({
  healthy: 'level-dot bg-green-500',
  warning: 'level-dot bg-amber-500',
  failed: 'level-dot bg-red-500',
  paused: 'level-dot bg-slate-400',
  idle: 'level-dot bg-blue-500',
}[level])

const getRunLevelText = (level: RunLevel) => ({
  success: '成功',
  failed: '失败',
  internal_failed: '内部失败',
  skipped: '跳过',
}[level])

const getRunLevelClass = (level: RunLevel) => ({
  success: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  internal_failed: 'bg-amber-100 text-amber-700',
  skipped: 'bg-slate-100 text-slate-500',
}[level])

const getRunLevelTextClass = (level: RunLevel) => ({
  success: 'text-green-600',
  failed: 'text-red-500',
  internal_failed: 'text-amber-500',
  skipped: 'text-slate-400',
}[level])

const getRunLevelMark = (level: RunLevel) => ({
  success: '✓',
  failed: '✗',
  internal_failed: '!',
  skipped: '-',
}[level])

const getRunRowClass = (level: RunLevel) => ({
  success: 'run-row-success',
  failed: 'run-row-failed',
  internal_failed: 'run-row-warning',
  skipped: 'run-row-skipped',
}[level])

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

.scheduler-stat {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
}

.scheduler-stat span {
  color: #64748b;
  font-size: 12px;
}

.scheduler-stat strong {
  color: #0f172a;
  font-size: 20px;
  line-height: 1;
}

.level-strip {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.level-pill {
  align-items: center;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-left-width: 3px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  padding: 9px 10px;
}

.level-pill span {
  color: #64748b;
  font-size: 12px;
}

.level-pill strong {
  color: #0f172a;
  font-size: 16px;
}

.level-healthy {
  border-left-color: #22c55e;
}

.level-warning {
  border-left-color: #f59e0b;
}

.level-failed {
  border-left-color: #ef4444;
}

.level-paused {
  border-left-color: #94a3b8;
}

.level-idle {
  border-left-color: #3b82f6;
}

.task-level-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.task-level-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-level-heading {
  align-items: center;
  color: #475569;
  display: flex;
  font-size: 13px;
  gap: 8px;
}

.task-level-heading span:last-child {
  color: #94a3b8;
  font-size: 12px;
}

.level-dot {
  border-radius: 999px;
  display: inline-block;
  height: 8px;
  width: 8px;
}

.history-levels {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.history-levels span {
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  padding: 5px 8px;
}

code {
  font-family: 'Courier New', monospace;
}

table {
  border-collapse: collapse;
  font-size: 13px;
  table-layout: fixed;
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

.scheduler-history-table th:nth-child(1),
.scheduler-history-table td:nth-child(1) {
  width: 150px;
}

.scheduler-history-table th:nth-child(2),
.scheduler-history-table td:nth-child(2) {
  width: 90px;
}

.scheduler-history-table th:nth-child(3),
.scheduler-history-table td:nth-child(3),
.scheduler-history-table th:nth-child(4),
.scheduler-history-table td:nth-child(4) {
  width: 92px;
}

.scheduler-history-table th:nth-child(5),
.scheduler-history-table td:nth-child(5) {
  width: 70px;
}

.scheduler-history-table th:nth-child(7),
.scheduler-history-table td:nth-child(7) {
  width: 160px;
}

.result-cell {
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-row-failed td {
  background: #fef2f2;
}

.run-row-warning td {
  background: #fffbeb;
}

.run-row-skipped td {
  background: #f8fafc;
}

@media (max-width: 900px) {
  .grid.grid-cols-2 {
    grid-template-columns: minmax(0, 1fr);
  }

  .grid.grid-cols-4,
  .level-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .scheduler-page {
    overflow-x: auto;
  }
}
</style>
