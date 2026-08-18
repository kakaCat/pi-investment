<template>
  <div class="system-logs">
    <el-card>
      <template #header>
        <div class="header">
          <span>系统日志</span>
          <div class="filters">
            <el-select v-model="filters.level" placeholder="日志级别" clearable style="width: 120px">
              <el-option label="DEBUG" value="debug" />
              <el-option label="INFO" value="info" />
              <el-option label="WARNING" value="warning" />
              <el-option label="ERROR" value="error" />
            </el-select>
            <el-date-picker
              v-model="filters.dateRange"
              type="datetimerange"
              range-separator="至"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              style="margin-left: 10px"
            />
            <el-button type="primary" @click="loadLogs" style="margin-left: 10px">
              查询
            </el-button>
            <el-button @click="clearFilters" style="margin-left: 10px">
              重置
            </el-button>
          </div>
        </div>
      </template>

      <!-- 日志列表 -->
      <div class="log-viewer">
        <div
          v-for="(log, index) in logs"
          :key="index"
          class="log-entry"
          :class="`log-${log.level}`"
        >
          <div class="log-header">
            <el-tag :type="getLevelType(log.level)" size="small">{{ log.level.toUpperCase() }}</el-tag>
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span class="log-source">{{ log.source }}</span>
          </div>
          <div class="log-message">{{ log.message }}</div>
          <div v-if="log.details" class="log-details">
            <el-button link size="small" @click="toggleDetails(index)">
              {{ expandedLogs.has(index) ? '收起' : '展开详情' }}
            </el-button>
            <pre v-if="expandedLogs.has(index)" class="details-content">{{
              JSON.stringify(log.details, null, 2)
            }}</pre>
          </div>
        </div>
        
        <el-empty v-if="logs.length === 0 && !loading" description="暂无日志" />
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[50, 100, 200, 500]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadLogs"
          @current-change="loadLogs"
        />
      </div>

      <!-- 加载状态 -->
      <div v-loading="loading" class="loading-overlay" v-if="loading"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { systemApi } from '@/api/system'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const logs = ref<any[]>([])
const expandedLogs = ref<Set<number>>(new Set())
const filters = ref({
  level: '',
  dateRange: null as [Date, Date] | null,
})
const currentPage = ref(1)
const pageSize = ref(100)
const total = ref(0)

const getLevelType = (level: string) => {
  const types: Record<string, any> = {
    debug: 'info',
    info: 'success',
    warning: 'warning',
    error: 'danger',
  }
  return types[level] || 'info'
}

const toggleDetails = (index: number) => {
  if (expandedLogs.value.has(index)) {
    expandedLogs.value.delete(index)
  } else {
    expandedLogs.value.add(index)
  }
}

const loadLogs = async () => {
  loading.value = true
  try {
    const params: any = {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    }

    if (filters.value.level) {
      params.level = filters.value.level
    }

    const result = await systemApi.getLogs(params)
    logs.value = result.logs || []
    total.value = result.total || 0
  } catch (e) {
    console.error('加载日志失败:', e)
    ElMessage.error('加载日志失败')
  } finally {
    loading.value = false
  }
}

const clearFilters = () => {
  filters.value = {
    level: '',
    dateRange: null,
  }
  currentPage.value = 1
  loadLogs()
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.system-logs {
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

.log-viewer {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  min-height: 400px;
  max-height: 600px;
  overflow-y: auto;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 15px;
  border-radius: 4px;
}

.log-entry {
  margin-bottom: 12px;
  padding: 10px;
  border-left: 3px solid #666;
  background: rgba(255, 255, 255, 0.05);
}

.log-entry.log-debug {
  border-left-color: #909399;
}

.log-entry.log-info {
  border-left-color: #67c23a;
}

.log-entry.log-warning {
  border-left-color: #e6a23c;
}

.log-entry.log-error {
  border-left-color: #f56c6c;
}

.log-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.log-time {
  color: #909399;
  font-size: 12px;
}

.log-source {
  color: #409eff;
  font-size: 12px;
}

.log-message {
  margin-left: 60px;
  line-height: 1.6;
}

.log-details {
  margin-top: 8px;
  margin-left: 60px;
}

.details-content {
  margin-top: 8px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
  color: #67c23a;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.loading-overlay {
  min-height: 100px;
}
</style>
