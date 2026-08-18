<template>
  <div class="alert-rules">
    <el-card>
      <template #header>
        <div class="header">
          <span>告警规则</span>
          <el-button type="primary" @click="showAddDialog = true">
            <el-icon><Plus /></el-icon>
            添加规则
          </el-button>
        </div>
      </template>

      <el-table :data="rules" v-loading="loading" stripe>
        <el-table-column prop="name" label="规则名称" min-width="150" />
        <el-table-column prop="condition" label="触发条件" min-width="200" />
        <el-table-column prop="level" label="告警级别" width="100">
          <template #default="{ row }">
            <el-tag :type="getLevelType(row.level)">{{ getLevelName(row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              @change="toggleRule(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="triggered_count" label="触发次数" width="120" />
        <el-table-column prop="last_triggered_at" label="最近触发" width="180">
          <template #default="{ row }">
            {{ row.last_triggered_at ? formatTime(row.last_triggered_at) : '从未' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="editRule(row)">
              编辑
            </el-button>
            <el-popconfirm
              title="确定删除这条规则吗？"
              @confirm="deleteRule(row.id)"
            >
              <template #reference>
                <el-button link type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="showAddDialog"
      :title="editingRule ? '编辑规则' : '添加规则'"
      width="600px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="规则名称">
          <el-input v-model="form.name" placeholder="例如：任务失败告警" />
        </el-form-item>
        <el-form-item label="事件类型">
          <el-select v-model="form.event_type" placeholder="选择事件类型">
            <el-option label="任务" value="task" />
            <el-option label="决策" value="decision" />
            <el-option label="系统" value="system" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发条件">
          <el-input
            v-model="form.condition"
            type="textarea"
            :rows="3"
            placeholder="例如：status == 'failed'"
          />
        </el-form-item>
        <el-form-item label="告警级别">
          <el-select v-model="form.level">
            <el-option label="信息" value="info" />
            <el-option label="警告" value="warning" />
            <el-option label="错误" value="error" />
            <el-option label="严重" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="通知渠道">
          <el-select v-model="form.channels" multiple placeholder="选择通知渠道">
            <el-option
              v-for="channel in channels"
              :key="channel.id"
              :label="channel.name"
              :value="channel.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { eventApi } from '@/api/events'
import { notificationApi } from '@/api/notifications'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const rules = ref<any[]>([])
const channels = ref<any[]>([])
const showAddDialog = ref(false)
const editingRule = ref<any>(null)
const form = ref({
  name: '',
  event_type: '',
  condition: '',
  level: 'warning',
  channels: [] as string[],
  enabled: true,
})

const getLevelType = (level: string) => {
  const types: Record<string, any> = {
    info: 'info',
    warning: 'warning',
    error: 'danger',
    critical: 'danger',
  }
  return types[level] || 'info'
}

const getLevelName = (level: string) => {
  const names: Record<string, string> = {
    info: '信息',
    warning: '警告',
    error: '错误',
    critical: '严重',
  }
  return names[level] || level
}

const loadRules = async () => {
  loading.value = true
  try {
    const result = await eventApi.getAlertRules()
    rules.value = result.rules || []
  } catch (e) {
    console.error('加载规则失败:', e)
    ElMessage.error('加载规则失败')
  } finally {
    loading.value = false
  }
}

const loadChannels = async () => {
  try {
    const result = await notificationApi.getChannels()
    channels.value = result.channels || []
  } catch (e) {
    console.error('加载渠道失败:', e)
  }
}

const editRule = (rule: any) => {
  editingRule.value = rule
  form.value = {
    name: rule.name,
    event_type: rule.event_type,
    condition: rule.condition,
    level: rule.level,
    channels: rule.channels || [],
    enabled: rule.enabled,
  }
  showAddDialog.value = true
}

const saveRule = async () => {
  if (!form.value.name) {
    ElMessage.warning('请输入规则名称')
    return
  }

  try {
    await eventApi.createAlertRule(form.value)
    ElMessage.success(editingRule.value ? '更新成功' : '添加成功')
    showAddDialog.value = false
    editingRule.value = null
    await loadRules()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

const deleteRule = async (id: string) => {
  try {
    await eventApi.deleteAlertRule(id)
    ElMessage.success('删除成功')
    await loadRules()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const toggleRule = async (rule: any) => {
  try {
    // TODO: 调用后端 API 更新状态
    ElMessage.success(rule.enabled ? '已启用' : '已禁用')
  } catch (e) {
    ElMessage.error('操作失败')
    rule.enabled = !rule.enabled
  }
}

onMounted(() => {
  loadRules()
  loadChannels()
})
</script>

<style scoped>
.alert-rules {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
