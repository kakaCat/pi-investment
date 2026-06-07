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

    <!-- 任务列表 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-4">
      <table class="w-full scheduler-task-table">
        <thead>
          <tr class="bg-slate-50 border-b border-slate-200">
            <th class="w-8"></th>
            <th>任务名称</th>
            <th>描述</th>
            <th>状态</th>
            <th>Cron</th>
            <th>命令</th>
            <th>上次运行</th>
            <th>下次执行</th>
            <th class="text-center">操作</th>
          </tr>
        </thead>
        <tbody class="text-sm">
          <tr
            v-for="task in taskLevelGroups.flatMap(g => g.tasks)"
            :key="task.id"
            class="border-b border-slate-100 hover:bg-slate-50"
            :class="getTaskRowClass(task.level)"
          >
            <td class="text-center">
              <span
                class="inline-block w-2 h-2 rounded-full"
                :class="task.enabled ? 'bg-green-500' : 'bg-slate-400'"
                :title="task.enabled ? '已启用' : '已暂停'"
              />
              <span
                v-if="isTaskActionLocked(task)"
                class="inline-block w-2 h-2 rounded-full bg-blue-500 animate-pulse ml-1"
                :title="isTaskTriggering(task) ? '触发中' : '运行中'"
              />
            </td>
            <td class="font-medium text-slate-800">{{ task.name }}</td>
            <td class="text-slate-600 text-xs" :title="task.description">
              {{ task.description || '-' }}
            </td>
            <td>
              <span class="text-xs px-2 py-0.5 rounded-full whitespace-nowrap" :class="getTaskLevelClass(task.level)">
                {{ getTaskLevelText(task.level) }}
              </span>
            </td>
            <td class="font-mono text-xs">{{ task.cron }}</td>
            <td class="text-xs">{{ task.command }}</td>
            <td class="text-xs">
              {{ task.lastRun ? formatDateTime(task.lastRun) : '-' }}
              <span v-if="task.lastStatus" :class="getRunLevelTextClass(task.lastStatus)" class="ml-1">
                {{ getRunLevelMark(task.lastStatus) }}
              </span>
            </td>
            <td class="text-xs">{{ task.nextRun ? formatDateTime(task.nextRun) : '-' }}</td>
            <td>
              <div class="flex items-center justify-center gap-1">
                <button
                  v-if="task.enabled && !isTaskActionLocked(task)"
                  class="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-100 transition-colors"
                  @click="handleTriggerTask(task)"
                  title="立即触发任务"
                >
                  触发
                </button>
                <button
                  v-if="task.enabled && isTaskActionLocked(task)"
                  class="text-xs px-2 py-1 border border-blue-200 rounded text-blue-500 bg-blue-50 cursor-not-allowed"
                  disabled
                  :title="isTaskTriggering(task) ? '任务正在触发，不可重复点击' : '任务运行中，不可重复触发'"
                >
                  {{ isTaskTriggering(task) ? '触发中...' : '运行中...' }}
                </button>
                <button
                  v-if="!task.enabled"
                  class="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-100 transition-colors"
                  @click="handleToggleTask(task)"
                  title="启用任务"
                >
                  启用
                </button>
                <button
                  v-if="task.enabled"
                  class="text-xs px-2 py-1 border border-slate-200 rounded hover:bg-slate-100 transition-colors"
                  :disabled="isTaskActionLocked(task)"
                  :class="{ 'opacity-50 cursor-not-allowed': isTaskActionLocked(task) }"
                  @click="handleToggleTask(task)"
                  :title="isTaskActionLocked(task) ? '任务处理中，无法暂停' : '暂停任务'"
                >
                  暂停
                </button>
                <button
                  class="text-xs px-2 py-1 border border-red-200 rounded text-red-500 hover:bg-red-50 transition-colors"
                  :disabled="isTaskActionLocked(task)"
                  :class="{ 'opacity-50 cursor-not-allowed': isTaskActionLocked(task) }"
                  @click="handleDeleteTask(task)"
                  :title="isTaskActionLocked(task) ? '任务处理中，无法删除' : '删除任务'"
                >
                  删除
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="taskLevelGroups.flatMap(g => g.tasks).length === 0">
            <td colspan="9" class="text-center text-slate-400 py-8">暂无任务</td>
          </tr>
        </tbody>
      </table>
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
            <td>{{ formatDateTime(row.startTime) }}</td>
            <td>{{ formatDateTime(row.endTime) }}</td>
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
        <el-button type="primary" @click="handleSaveTask">保存</el-button>
      </template>
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
import { formatDateTime } from '@/utils/format'
import { useScheduler } from '@/composables/useScheduler'
import type { Task, TaskForm, TaskLevel, RunLevel } from '@/types/scheduler'

// ========== 使用 Composable ==========
const {
  // 任务列表
  // loading,  // 暂未在模板中使用
  // tasks,    // 暂未在模板中使用
  taskPage,
  taskPageSize,
  taskTotal,
  taskStats,
  taskLevelStats,
  taskLevelGroups,
  loadTasks,
  handleTaskPageSizeChange,
  createTask,
  updateTask,
  triggerTask,
  isTaskTriggering,
  toggleTask,
  deleteTask,

  // 运行历史
  history,
  historyPage,
  historyPageSize,
  historyTotal,
  historyLevelStats,
  loadHistory,
  handleHistoryPageSizeChange,

  // 工具函数
  getTaskLevelText,
  getRunLevelText,
} = useScheduler()

// ========== 对话框状态 ==========
const taskDialogVisible = ref(false)
const cronHelpVisible = ref(false)
const isEdit = ref(false)

// ========== 任务表单 ==========
const taskForm = reactive<TaskForm>({
  name: '',
  command: '',
  cron: '',
  params: '',
  description: '',
  enabled: true,
})

// ========== 对话框操作 ==========

/**
 * 显示新建任务对话框
 */
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

/**
 * 保存任务（创建或更新）
 */
const handleSaveTask = async () => {
  if (!taskForm.name || !taskForm.command || !taskForm.cron) {
    return
  }

  try {
    if (isEdit.value && taskForm.id) {
      await updateTask(taskForm)
    } else {
      await createTask(taskForm)
    }
    taskDialogVisible.value = false
  } catch (error: any) {
    // 错误已在 composable 中处理
  }
}

/**
 * 显示 Cron 帮助
 */
const showCronHelper = () => {
  cronHelpVisible.value = true
}

// ========== 任务操作包装 ==========

/**
 * 触发任务
 */
const handleTriggerTask = async (task: Task) => {
  await triggerTask(task)
}

/**
 * 切换任务启用状态
 */
const handleToggleTask = async (task: Task) => {
  await toggleTask(task)
}

/**
 * 删除任务
 */
const handleDeleteTask = async (task: Task) => {
  await deleteTask(task)
}

const isTaskActionLocked = (task: Task) => task.isRunning || isTaskTriggering(task)

// ========== 工具函数 ==========

/**
 * 格式化耗时
 */
const formatDuration = (seconds: number) => {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${s}s`
}

/**
 * 获取任务级别样式类
 */
const getTaskLevelClass = (level: TaskLevel) => ({
  healthy: 'bg-green-100 text-green-700',
  warning: 'bg-amber-100 text-amber-700',
  failed: 'bg-red-100 text-red-700',
  paused: 'bg-slate-100 text-slate-500',
  idle: 'bg-blue-100 text-blue-700',
}[level])

/**
 * 获取任务级别边框样式类
 */
const getTaskLevelBorderClass = (level: TaskLevel) => ({
  healthy: 'level-healthy',
  warning: 'level-warning',
  failed: 'level-failed',
  paused: 'level-paused',
  idle: 'level-idle',
}[level])

/**
 * 获取运行级别样式类
 */
const getRunLevelClass = (level: RunLevel) => ({
  success: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  internal_failed: 'bg-amber-100 text-amber-700',
  skipped: 'bg-slate-100 text-slate-500',
}[level])

/**
 * 获取运行级别文本样式类
 */
const getRunLevelTextClass = (level: RunLevel) => ({
  success: 'text-green-600',
  failed: 'text-red-500',
  internal_failed: 'text-amber-500',
  skipped: 'text-slate-400',
}[level])

/**
 * 获取运行级别标记
 */
const getRunLevelMark = (level: RunLevel) => ({
  success: '✓',
  failed: '✗',
  internal_failed: '!',
  skipped: '-',
}[level])

/**
 * 获取运行行样式类
 */
const getRunRowClass = (level: RunLevel) => ({
  success: 'run-row-success',
  failed: 'run-row-failed',
  internal_failed: 'run-row-warning',
  skipped: 'run-row-skipped',
}[level])

/**
 * 获取任务行样式类
 */
const getTaskRowClass = (level: TaskLevel) => ({
  healthy: '',
  warning: 'task-row-warning',
  failed: 'task-row-failed',
  paused: 'task-row-paused',
  idle: '',
}[level])

// ========== 生命周期 ==========
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

/* ========== 任务表格样式 ========== */
.scheduler-task-table {
  border-collapse: collapse;
  font-size: 13px;
}

.scheduler-task-table th {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  padding: 12px 16px;
  text-align: left;
  white-space: nowrap;
}

.scheduler-task-table td {
  padding: 12px 16px;
  vertical-align: middle;
}

.scheduler-task-table tbody tr {
  transition: background-color 0.15s ease;
}

/* 任务行状态背景色 */
.task-row-failed {
  background: #fef2f2;
}

.task-row-warning {
  background: #fffbeb;
}

.task-row-paused {
  background: #f8fafc;
}

/* 描述列最大宽度 */
.scheduler-task-table td:nth-child(3) {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 旧的卡片样式（已移除，保留用于参考）*/
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
  width: 160px;
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
