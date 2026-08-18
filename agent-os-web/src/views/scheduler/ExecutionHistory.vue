<template>
  <div class="execution-history">
    <el-card>
      <template #header>
        <span>执行历史</span>
      </template>

      <!-- 筛选器 -->
      <div class="filters">
        <el-select v-model="taskFilter" placeholder="选择任务" clearable style="width: 200px">
          <el-option label="全部任务" value="" />
          <el-option v-for="task in tasks" :key="task.id" :label="task.name" :value="task.id" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 150px">
          <el-option label="全部状态" value="" />
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="运行中" value="running" />
        </el-select>
      </div>

      <!-- 执行记录表格 -->
      <el-table :data="filteredExecutions" stripe style="margin-top: 16px">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding: 20px">
              <h4>执行详情</h4>
              <p><strong>输出：</strong></p>
              <pre style="background: #f5f7fa; padding: 12px; border-radius: 4px">{{ row.output || '无' }}</pre>
              <p v-if="row.error"><strong>错误：</strong></p>
              <pre v-if="row.error" style="background: #fef0f0; padding: 12px; border-radius: 4px; color: #f56c6c">{{ row.error }}</pre>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="执行ID" width="150" show-overflow-tooltip />
        <el-table-column prop="task_name" label="任务名" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'"
            >
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="100" />
        <el-table-column prop="trigger_type" label="触发方式" width="120" />
        <el-table-column prop="started_at" label="开始时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.started_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="retryExecution(row.task_id)">
              重新执行
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="executions.length"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: center"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { schedulerApi } from '@/api/scheduler'
import { formatTime } from '@/utils/format'

const executions = ref<any[]>([])
const tasks = ref<any[]>([])
const taskFilter = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(10)

const filteredExecutions = computed(() => {
  let result = executions.value

  if (taskFilter.value) {
    result = result.filter((e) => e.task_id === taskFilter.value)
  }

  if (statusFilter.value) {
    result = result.filter((e) => e.status === statusFilter.value)
  }

  const start = (currentPage.value - 1) * pageSize.value
  return result.slice(start, start + pageSize.value)
})

const loadExecutions = async () => {
  try {
    const result = await schedulerApi.listExecutions({ limit: 100 })
    executions.value = result.executions || []

    // 从执行记录中提取任务列表用于筛选
    const taskMap = new Map()
    executions.value.forEach((e: any) => {
      if (e.task_id && !taskMap.has(e.task_id)) {
        taskMap.set(e.task_id, { id: e.task_id, name: e.task_name || e.task_id })
      }
    })
    tasks.value = Array.from(taskMap.values())
  } catch (e) {
    console.error('加载执行历史失败:', e)
    ElMessage.error('加载执行历史失败')
  }
}

const retryExecution = async (taskId: string) => {
  try {
    await schedulerApi.triggerTask(taskId)
    ElMessage.success('任务已重新触发')
  } catch (e) {
    ElMessage.error('触发失败')
  }
}

onMounted(() => {
  loadExecutions()
})
</script>

<style scoped>
.execution-history {
  padding: 20px;
}
.filters {
  display: flex;
  gap: 12px;
}
</style>
