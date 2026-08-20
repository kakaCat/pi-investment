<template>
  <div class="channel-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>通知渠道</span>
          <el-button type="primary" @click="showAddDialog = true">
            <el-icon><Plus /></el-icon>
            添加渠道
          </el-button>
        </div>
      </template>

      <el-table :data="channels" v-loading="loading" stripe>
        <el-table-column prop="name" label="渠道名称" width="150" />
        <el-table-column prop="code" label="标识" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">
              {{ row.enabled ? '已启用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="config" label="配置" min-width="200">
          <template #default="{ row }">
            <el-text truncated>{{ formatConfig(row.config) }}</el-text>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              title="确定删除这个渠道吗？"
              @confirm="deleteChannel(row.id)"
            >
              <template #reference>
                <el-button link type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && channels.length === 0" description="暂无通知渠道" />
    </el-card>

    <!-- 添加渠道对话框 -->
    <el-dialog v-model="showAddDialog" title="添加渠道" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="渠道标识">
          <el-input v-model="form.code" placeholder="例如：alerts" />
        </el-form-item>
        <el-form-item label="渠道名称">
          <el-input v-model="form.name" placeholder="例如：告警群" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="渠道用途描述" />
        </el-form-item>
        <el-form-item label="配置">
          <el-input
            v-model="form.config"
            type="textarea"
            :rows="6"
            placeholder='JSON 格式配置，例如：{"webhook": "https://..."}'
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveChannel">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { notificationApi } from '@/api/notifications'
import { formatTime } from '@/utils/format'

interface Channel {
  id: string
  code: string
  name: string
  enabled: boolean
  config: any
  created_at: string
}

const loading = ref(false)
const saving = ref(false)
const channels = ref<Channel[]>([])
const showAddDialog = ref(false)
const form = ref({
  code: '',
  name: '',
  description: '',
  config: '{}',
  enabled: true,
})

const formatConfig = (config: any) => {
  if (!config) return '-'
  if (typeof config === 'string') return config
  return JSON.stringify(config)
}

const loadChannels = async () => {
  loading.value = true
  try {
    const result = await notificationApi.getChannels()
    channels.value = result.channels || []
  } catch (e) {
    console.error('加载渠道失败:', e)
    ElMessage.error('加载渠道失败')
  } finally {
    loading.value = false
  }
}

const saveChannel = async () => {
  if (!form.value.code || !form.value.name) {
    ElMessage.warning('请填写渠道标识和名称')
    return
  }

  let configObj: any
  try {
    configObj = JSON.parse(form.value.config)
  } catch (e) {
    ElMessage.error('配置格式错误，请输入有效的 JSON')
    return
  }

  saving.value = true
  try {
    await notificationApi.createChannel({
      code: form.value.code,
      name: form.value.name,
      description: form.value.description || undefined,
      enabled: form.value.enabled,
      config: configObj,
    })
    ElMessage.success('添加成功')
    showAddDialog.value = false
    form.value = { code: '', name: '', description: '', config: '{}', enabled: true }
    await loadChannels()
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const deleteChannel = async (id: string) => {
  try {
    await notificationApi.deleteChannel(id)
    ElMessage.success('删除成功')
    await loadChannels()
  } catch (e) {
    console.error('删除失败:', e)
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadChannels()
})
</script>

<style scoped>
.channel-list {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
