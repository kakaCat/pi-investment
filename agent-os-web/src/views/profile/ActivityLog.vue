<template>
  <div class="activity-log">
    <el-card>
      <template #header>
        <div class="header">
          <span>操作记录</span>
          <div class="filters">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 300px"
            />
            <el-select v-model="filters.action" placeholder="操作类型" clearable style="width: 150px; margin-left: 10px">
              <el-option label="创建" value="create" />
              <el-option label="更新" value="update" />
              <el-option label="删除" value="delete" />
              <el-option label="执行" value="execute" />
            </el-select>
            <el-button type="primary" @click="loadLogs" style="margin-left: 10px">
              查询
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="action" label="操作" width="100">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)">
              {{ getActionName(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="资源类型" width="120" />
        <el-table-column prop="resource_name" label="资源名称" min-width="200" />
        <el-table-column prop="description" label="描述" min-width="250" />
        <el-table-column prop="ip_address" label="IP 地址" width="150" />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadLogs"
          @current-change="loadLogs"
        />
      </div>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="操作详情" width="600px">
      <el-descriptions :column="1" border v-if="selectedLog">
        <el-descriptions-item label="操作类型">
          <el-tag :type="getActionType(selectedLog.action)">
            {{ getActionName(selectedLog.action) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="资源类型">{{ selectedLog.resource_type }}</el-descriptions-item>
        <el-descriptions-item label="资源名称">{{ selectedLog.resource_name }}</el-descriptions-item>
        <el-descriptions-item label="描述">{{ selectedLog.description }}</el-descriptions-item>
        <el-descriptions-item label="IP 地址">{{ selectedLog.ip_address }}</el-descriptions-item>
        <el-descriptions-item label="User Agent">{{ selectedLog.user_agent }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatTime(selectedLog.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="详细信息" v-if="selectedLog.details">
          <pre style="white-space: pre-wrap; word-wrap: break-word;">{{
            JSON.stringify(selectedLog.details, null, 2)
          }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { formatTime } from '@/utils/format'

interface Log {
  id: string
  action: string
  resource_type: string
  resource_name: string
  description: string
  ip_address: string
  user_agent?: string
  created_at: string
  details?: any
}

const loading = ref(false)
const logs = ref<Log[]>([])
const dateRange = ref<[Date, Date] | null>(null)
const filters = ref({
  action: '',
})
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showDetailDialog = ref(false)
const selectedLog = ref<Log | null>(null)

const getActionType = (action: string) => {
  const types: Record<string, any> = {
    create: 'success',
    update: 'warning',
    delete: 'danger',
    execute: 'primary',
  }
  return types[action] || 'info'
}

const getActionName = (action: string) => {
  const names: Record<string, string> = {
    create: '创建',
    update: '更新',
    delete: '删除',
    execute: '执行',
  }
  return names[action] || action
}

const loadLogs = async () => {
  loading.value = true
  try {
    // TODO: 调用后端 API
    // 模拟数据
    logs.value = [
      {
        id: '1',
        action: 'create',
        resource_type: 'task',
        resource_name: '每日数据同步',
        description: '创建新任务',
        ip_address: '127.0.0.1',
        user_agent: 'Mozilla/5.0',
        created_at: new Date().toISOString(),
        details: { cron: '0 0 * * *' },
      },
      {
        id: '2',
        action: 'execute',
        resource_type: 'task',
        resource_name: '每日数据同步',
        description: '手动触发任务执行',
        ip_address: '127.0.0.1',
        user_agent: 'Mozilla/5.0',
        created_at: new Date(Date.now() - 3600000).toISOString(),
      },
      {
        id: '3',
        action: 'update',
        resource_type: 'skill',
        resource_name: 'data_processor',
        description: '更新技能配置',
        ip_address: '127.0.0.1',
        user_agent: 'Mozilla/5.0',
        created_at: new Date(Date.now() - 7200000).toISOString(),
      },
    ]
    total.value = 3
  } catch (e) {
    console.error('加载日志失败:', e)
    ElMessage.error('加载日志失败')
  } finally {
    loading.value = false
  }
}

const viewDetail = (log: Log) => {
  selectedLog.value = log
  showDetailDialog.value = true
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.activity-log {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filters {
  display: flex;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
