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
        <el-table-column prop="type" label="渠道类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ getChannelTypeName(row.type) }}</el-tag>
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
        <el-table-column prop="last_sent_at" label="最近发送" width="180">
          <template #default="{ row }">
            {{ row.last_sent_at ? formatTime(row.last_sent_at) : '从未发送' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="editChannel(row)">
              编辑
            </el-button>
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
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="showAddDialog"
      :title="editingChannel ? '编辑渠道' : '添加渠道'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="渠道名称">
          <el-input v-model="form.name" placeholder="例如：Feishu Bot" />
        </el-form-item>
        <el-form-item label="渠道类型">
          <el-select v-model="form.type" placeholder="选择类型">
            <el-option label="飞书" value="feishu" />
            <el-option label="钉钉" value="dingtalk" />
            <el-option label="企业微信" value="wechat" />
            <el-option label="邮件" value="email" />
            <el-option label="Webhook" value="webhook" />
          </el-select>
        </el-form-item>
        <el-form-item label="配置">
          <el-input
            v-model="form.config"
            type="textarea"
            :rows="6"
            placeholder="JSON 格式配置"
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveChannel">保存</el-button>
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
  name: string
  type: string
  enabled: boolean
  config: any
  last_sent_at?: string
}

const loading = ref(false)
const channels = ref<Channel[]>([])
const showAddDialog = ref(false)
const editingChannel = ref<Channel | null>(null)
const form = ref({
  name: '',
  type: '',
  config: '{}',
  enabled: true,
})

const getChannelTypeName = (type: string) => {
  const names: Record<string, string> = {
    feishu: '飞书',
    dingtalk: '钉钉',
    wechat: '企业微信',
    email: '邮件',
    webhook: 'Webhook',
  }
  return names[type] || type
}

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

const editChannel = (channel: Channel) => {
  editingChannel.value = channel
  form.value = {
    name: channel.name,
    type: channel.type,
    config: typeof channel.config === 'string' ? channel.config : JSON.stringify(channel.config, null, 2),
    enabled: channel.enabled,
  }
  showAddDialog.value = true
}

const saveChannel = async () => {
  try {
    // 验证 JSON
    JSON.parse(form.value.config)
    
    // TODO: 调用后端 API 保存
    ElMessage.success(editingChannel.value ? '更新成功' : '添加成功')
    showAddDialog.value = false
    await loadChannels()
  } catch (e) {
    ElMessage.error('配置格式错误，请输入有效的 JSON')
  }
}

const deleteChannel = async (id: string) => {
  try {
    // TODO: 调用后端 API 删除
    ElMessage.success('删除成功')
    await loadChannels()
  } catch (e) {
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
