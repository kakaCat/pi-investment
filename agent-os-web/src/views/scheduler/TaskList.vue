<template>
  <div class="task-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>任务列表</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            新建任务
          </el-button>
        </div>
      </template>

      <!-- 搜索和筛选 -->
      <div class="filters">
        <el-input
          v-model="searchText"
          placeholder="搜索任务名称"
          clearable
          style="width: 300px"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="statusFilter" placeholder="状态筛选" clearable style="width: 150px">
          <el-option label="全部" value="" />
          <el-option label="启用" value="enabled" />
          <el-option label="停用" value="disabled" />
        </el-select>
      </div>

      <!-- 任务表格 -->
      <el-table :data="filteredTasks" stripe style="margin-top: 16px">
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="cron" label="Cron" width="150">
          <template #default="{ row }">
            <el-tooltip :content="row.cron" placement="top">
              <span>{{ cronToChinese(row.cron) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">
              {{ row.enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="所有者" width="120" />
        <el-table-column prop="webhook_url" label="Webhook" width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="triggerTask(row.id)">
              <el-icon><VideoPlay /></el-icon>
              触发
            </el-button>
            <el-button
              v-if="row.enabled"
              size="small"
              type="warning"
              @click="pauseTask(row.id)"
            >
              <el-icon><VideoPause /></el-icon>
              暂停
            </el-button>
            <el-button
              v-else
              size="small"
              type="success"
              @click="resumeTask(row.id)"
            >
              <el-icon><VideoPlay /></el-icon>
              恢复
            </el-button>
            <el-button size="small" type="danger" @click="deleteTask(row.id)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="tasks.length"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: center"
      />
    </el-card>

    <!-- 新建任务对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建任务" width="600px">
      <el-form :model="newTask" label-width="120px">
        <el-form-item label="名称" required>
          <el-input v-model="newTask.name" placeholder="任务名称" />
        </el-form-item>
        <el-form-item label="Cron 表达式" required>
          <el-input v-model="newTask.cron" placeholder="0 9 * * 1-5" />
        </el-form-item>
        <el-form-item label="Webhook URL">
          <el-input v-model="newTask.webhook_url" placeholder="http://..." />
        </el-form-item>
        <el-form-item label="Payload (JSON)">
          <el-input
            v-model="newTask.payload"
            type="textarea"
            :rows="4"
            placeholder='{"key": "value"}'
          />
        </el-form-item>
        <el-form-item label="超时（秒）">
          <el-input-number v-model="newTask.timeout" :min="1" :max="86400" />
        </el-form-item>
        <el-form-item label="重试次数">
          <el-input-number v-model="newTask.retry_count" :min="0" :max="5" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="newTask.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, VideoPlay, VideoPause, Delete } from '@element-plus/icons-vue'
import { schedulerApi } from '@/api/scheduler'
import type { Task } from '@/types'
import { cronToChinese } from '@/utils/format'

const tasks = ref<Task[]>([])
const searchText = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const showCreateDialog = ref(false)

const newTask = ref({
  name: '',
  cron: '',
  webhook_url: '',
  payload: '',
  timeout: 3600,
  retry_count: 0,
  enabled: true,
})

const filteredTasks = computed(() => {
  let result = tasks.value

  if (searchText.value) {
    result = result.filter((t) => t.name.includes(searchText.value))
  }

  if (statusFilter.value === 'enabled') {
    result = result.filter((t) => t.enabled)
  } else if (statusFilter.value === 'disabled') {
    result = result.filter((t) => !t.enabled)
  }

  const start = (currentPage.value - 1) * pageSize.value
  return result.slice(start, start + pageSize.value)
})

const loadTasks = async () => {
  try {
    // Mock 数据
    tasks.value = Array.from({ length: 15 }, (_, i) => ({
      id: `task-${i}`,
      name: `task_${i}`,
      owner: 'agent-ts',
      cron: i % 3 === 0 ? '0 2 * * *' : '40 17 * * 1-5',
      webhook_url: 'http://localhost:3002/api/webhook/trigger',
      payload: {},
      timeout: 3600,
      retry_count: 0,
      enabled: i % 4 !== 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }))

    // 尝试获取真实数据
    // const result = await schedulerApi.listTasks()
    // tasks.value = result.tasks
  } catch (e) {
    console.error('加载任务失败:', e)
  }
}

const createTask = async () => {
  try {
    // await schedulerApi.createTask(newTask.value)
    ElMessage.success('任务创建成功（Mock）')
    showCreateDialog.value = false
    await loadTasks()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

const triggerTask = async (id: string) => {
  try {
    // await schedulerApi.triggerTask(id)
    ElMessage.success('任务已触发（Mock）')
  } catch (e) {
    ElMessage.error('触发失败')
  }
}

const pauseTask = async (id: string) => {
  try {
    // await schedulerApi.pauseTask(id)
    ElMessage.success('任务已暂停（Mock）')
    await loadTasks()
  } catch (e) {
    ElMessage.error('暂停失败')
  }
}

const resumeTask = async (id: string) => {
  try {
    // await schedulerApi.resumeTask(id)
    ElMessage.success('任务已恢复（Mock）')
    await loadTasks()
  } catch (e) {
    ElMessage.error('恢复失败')
  }
}

const deleteTask = async (id: string) => {
  try {
    await ElMessageBox.confirm('确认删除该任务？', '警告', {
      type: 'warning',
    })
    // await schedulerApi.deleteTask(id)
    ElMessage.success('任务已删除（Mock）')
    await loadTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.task-list {
  padding: 20px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filters {
  display: flex;
  gap: 12px;
}
</style>
