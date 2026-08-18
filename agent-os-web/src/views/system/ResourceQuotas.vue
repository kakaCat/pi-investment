<template>
  <div class="resource-quotas">
    <el-card>
      <template #header>
        <span>资源配额</span>
      </template>

      <el-table :data="quotas" v-loading="loading" stripe>
        <el-table-column prop="namespace" label="命名空间" width="150" />
        <el-table-column prop="resource_type" label="资源类型" width="150" />
        <el-table-column prop="limit" label="限制" width="120" />
        <el-table-column prop="used" label="已用" width="120" />
        <el-table-column label="使用率" width="200">
          <template #default="{ row }">
            <el-progress
              :percentage="getUsagePercent(row)"
              :color="getUsageColor(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row)">
              {{ getStatusText(row) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { systemApi } from '@/api/system'

const loading = ref(false)
const quotas = ref<any[]>([])

const getUsagePercent = (row: any) => {
  if (!row.limit || row.limit === 0) return 0
  return Math.round((row.used / row.limit) * 100)
}

const getUsageColor = (row: any) => {
  const percent = getUsagePercent(row)
  if (percent >= 90) return '#f56c6c'
  if (percent >= 70) return '#e6a23c'
  return '#67c23a'
}

const getStatusType = (row: any) => {
  const percent = getUsagePercent(row)
  if (percent >= 90) return 'danger'
  if (percent >= 70) return 'warning'
  return 'success'
}

const getStatusText = (row: any) => {
  const percent = getUsagePercent(row)
  if (percent >= 90) return '告警'
  if (percent >= 70) return '注意'
  return '正常'
}

const loadQuotas = async () => {
  loading.value = true
  try {
    const result = await systemApi.getQuotas()
    quotas.value = result.quotas || []
  } catch (e) {
    console.error('加载配额失败:', e)
    ElMessage.error('加载配额失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadQuotas()
})
</script>

<style scoped>
.resource-quotas {
  padding: 20px;
}
</style>
