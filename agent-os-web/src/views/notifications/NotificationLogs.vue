<template>
  <div class="notification-logs">
    <el-card>
      <template #header>
        <div class="header">
          <span>通知日志</span>
          <div class="filters">
            <el-select v-model="filters.channel" placeholder="选择渠道" clearable style="width: 150px">
              <el-option
                v-for="channel in channels"
                :key="channel.id"
                :label="channel.name"
                :value="channel.id"
              />
            </el-select>
            <el-select v-model="filters.status" placeholder="状态" clearable style="width: 120px; margin-left: 10px">
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
            </el-select>
            <el-button type="primary" @click="loadLogs" style="margin-left: 10px">
              查询
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="channel_name" label="渠道" width="150" />
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sent_at" label="发送时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.sent_at) }}
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
    <el-dialog v-model="showDetailDialog" title="通知详情" width="600px">
      <el-descriptions :column="1" border v-if="selectedLog">
        <el-descriptions-item label="渠道">{{ selectedLog.channel_name }}</el-descriptions-item>
        <el-descriptions-item label="标题">{{ selectedLog.title }}</el-descriptions-item>
        <el-descriptions-item label="内容">
          <pre style="white-space: pre-wrap; word-wrap: break-word;">{{ selectedLog.content }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="selectedLog.status === 'success' ? 'success' : 'danger'">
            {{ selectedLog.status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="发送时间">{{ formatTime(selectedLog.sent_at) }}</el-descriptions-item>
        <el-descriptions-item label="错误信息" v-if="selectedLog.error">
          <el-text type="danger">{{ selectedLog.error }}</el-text>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { notificationApi } from '@/api/notifications'
import { formatTime } from '@/utils/format'

interface Log {
  id: string
  channel_name: string
  title: string
  content: string
  status: string
  sent_at: string
  error?: string
}

interface Channel {
  id: string
  name: string
}

const loading = ref(false)
const logs = ref<Log[]>([])
const channels = ref<Channel[]>([])
const filters = ref({
  channel: '',
  status: '',
})
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showDetailDialog = ref(false)
const selectedLog = ref<Log | null>(null)

const loadChannels = async () => {
  try {
    const result = await notificationApi.getChannels()
    channels.value = result.channels || []
  } catch (e) {
    console.error('加载渠道失败:', e)
  }
}

const loadLogs = async () => {
  loading.value = true
  try {
    const result = await notificationApi.getLogs({
      limit: pageSize.value,
      ...filters.value,
    })
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
  loadChannels()
  loadLogs()
})
</script>

<style scoped>
.notification-logs {
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
