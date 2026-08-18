<template>
  <div class="event-history">
    <el-card>
      <template #header>
        <div class="header">
          <span>事件历史</span>
          <div class="filters">
            <el-select v-model="filters.type" placeholder="事件类型" clearable style="width: 150px">
              <el-option label="任务" value="task" />
              <el-option label="决策" value="decision" />
              <el-option label="记忆" value="memory" />
              <el-option label="系统" value="system" />
            </el-select>
            <el-date-picker
              v-model="filters.dateRange"
              type="datetimerange"
              range-separator="至"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              style="margin-left: 10px"
            />
            <el-button type="primary" @click="loadHistory" style="margin-left: 10px">
              查询
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="events" v-loading="loading" stripe>
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getEventTagType(row.type)">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="300" />
        <el-table-column prop="agent_id" label="Agent ID" width="150" />
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

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadHistory"
          @current-change="loadHistory"
        />
      </div>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="事件详情" width="600px">
      <el-descriptions :column="1" border v-if="selectedEvent">
        <el-descriptions-item label="类型">
          <el-tag :type="getEventTagType(selectedEvent.type)">{{ selectedEvent.type }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="消息">{{ selectedEvent.message }}</el-descriptions-item>
        <el-descriptions-item label="Agent ID">{{ selectedEvent.agent_id }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatTime(selectedEvent.timestamp) }}</el-descriptions-item>
        <el-descriptions-item label="详细数据" v-if="selectedEvent.data">
          <pre style="white-space: pre-wrap; word-wrap: break-word;">{{
            JSON.stringify(selectedEvent.data, null, 2)
          }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { eventApi } from '@/api/events'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const events = ref<any[]>([])
const filters = ref({
  type: '',
  dateRange: null as [Date, Date] | null,
})
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showDetailDialog = ref(false)
const selectedEvent = ref<any>(null)

const getEventTagType = (type: string) => {
  const types: Record<string, any> = {
    task: 'primary',
    decision: 'success',
    memory: 'info',
    system: 'warning',
  }
  return types[type] || 'info'
}

const loadHistory = async () => {
  loading.value = true
  try {
    const params: any = {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    }
    
    if (filters.value.type) {
      params.type = filters.value.type
    }
    
    if (filters.value.dateRange) {
      params.start = filters.value.dateRange[0].toISOString()
      params.end = filters.value.dateRange[1].toISOString()
    }

    const result = await eventApi.getHistory(params)
    events.value = result.events || []
    total.value = result.total || 0
  } catch (e) {
    console.error('加载事件历史失败:', e)
    ElMessage.error('加载事件历史失败')
  } finally {
    loading.value = false
  }
}

const viewDetail = (event: any) => {
  selectedEvent.value = event
  showDetailDialog.value = true
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.event-history {
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
