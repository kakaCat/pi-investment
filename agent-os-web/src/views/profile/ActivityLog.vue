<template>
  <div class="activity-log">
    <el-card>
      <template #header>
        <div class="header">
          <span>操作记录</span>
          <div class="filters">
            <el-select v-model="filters.action" placeholder="操作类型" clearable style="width: 150px">
              <el-option v-for="opt in actionOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
            <el-button type="primary" @click="loadLogs" style="margin-left: 10px">
              查询
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="action" label="操作" width="140">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)">
              {{ getActionName(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource" label="资源" min-width="200" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP 地址" width="140">
          <template #default="{ row }">
            {{ row.ip_address || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.timestamp) }}
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

      <el-empty v-if="!loading && logs.length === 0" description="暂无操作记录" />

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
        <el-descriptions-item label="资源">{{ selectedLog.resource || '-' }}</el-descriptions-item>
        <el-descriptions-item label="IP 地址">{{ selectedLog.ip_address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="User Agent">{{ selectedLog.user_agent || '-' }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatTime(selectedLog.timestamp) }}</el-descriptions-item>
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
import { profileApi } from '@/api/profile'
import { formatTime } from '@/utils/format'

interface Log {
  id: string
  action: string
  resource?: string
  ip_address?: string
  user_agent?: string
  timestamp: string
  details?: any
}

const loading = ref(false)
const logs = ref<Log[]>([])
const filters = ref({
  action: '',
})
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showDetailDialog = ref(false)
const selectedLog = ref<Log | null>(null)

const actionOptions = [
  { value: 'login', label: '登录' },
  { value: 'create', label: '创建' },
  { value: 'update', label: '更新' },
  { value: 'delete', label: '删除' },
  { value: 'view', label: '查看' },
  { value: 'execute', label: '执行' },
]

const getActionType = (action: string) => {
  const types: Record<string, any> = {
    login: 'primary',
    create: 'success',
    update: 'warning',
    delete: 'danger',
    execute: 'primary',
    view: 'info',
  }
  return types[action] || 'info'
}

const getActionName = (action: string) => {
  const names: Record<string, string> = {
    login: '登录',
    create: '创建',
    update: '更新',
    delete: '删除',
    execute: '执行',
    view: '查看',
  }
  return names[action] || action
}

const loadLogs = async () => {
  loading.value = true
  try {
    const params: any = { limit: pageSize.value }
    const result = await profileApi.getActivityLogs(params)
    logs.value = result.logs || []
    total.value = result.total || 0
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
