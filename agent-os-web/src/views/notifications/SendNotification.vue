<template>
  <div class="send-notification">
    <el-card>
      <template #header>
        <span>发送通知</span>
      </template>

      <el-form :model="form" label-width="100px" style="max-width: 600px">
        <el-form-item label="通知渠道" required>
          <el-select v-model="form.channel" placeholder="选择渠道">
            <el-option
              v-for="channel in enabledChannels"
              :key="channel.id"
              :label="channel.name"
              :value="channel.id"
            >
              <span>{{ channel.name }}</span>
              <el-tag size="small" style="margin-left: 10px">{{ getChannelTypeName(channel.type) }}</el-tag>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="通知标题" required>
          <el-input v-model="form.title" placeholder="输入通知标题" maxlength="100" show-word-limit />
        </el-form-item>

        <el-form-item label="通知内容" required>
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="8"
            placeholder="输入通知内容"
            maxlength="1000"
            show-word-limit
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="sendNotification" :loading="sending">
            <el-icon><Promotion /></el-icon>
            发送
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 快速模板 -->
      <el-divider content-position="left">快速模板</el-divider>
      <div class="templates">
        <el-card
          v-for="template in templates"
          :key="template.title"
          shadow="hover"
          class="template-card"
          @click="useTemplate(template)"
        >
          <h4>{{ template.title }}</h4>
          <p>{{ template.content.substring(0, 50) }}...</p>
        </el-card>
      </div>
    </el-card>

    <!-- 发送历史 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>最近发送</span>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="log in recentLogs"
          :key="log.id"
          :timestamp="formatTime(log.sent_at)"
          :type="log.status === 'success' ? 'success' : 'danger'"
        >
          <div>
            <el-tag size="small">{{ log.channel_name }}</el-tag>
            <span style="margin-left: 10px">{{ log.title }}</span>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion } from '@element-plus/icons-vue'
import { notificationApi } from '@/api/notifications'
import { formatTime } from '@/utils/format'

interface Channel {
  id: string
  name: string
  type: string
  enabled: boolean
}

interface Log {
  id: string
  channel_name: string
  title: string
  status: string
  sent_at: string
}

const sending = ref(false)
const channels = ref<Channel[]>([])
const recentLogs = ref<Log[]>([])
const form = ref({
  channel: '',
  title: '',
  content: '',
})

const templates = [
  {
    title: '任务执行完成',
    content: '任务 [任务名称] 已执行完成\n状态: 成功\n耗时: 10.5s\n结果: [结果摘要]',
  },
  {
    title: '任务执行失败',
    content: '任务 [任务名称] 执行失败\n错误: [错误信息]\n请检查日志并处理',
  },
  {
    title: '系统告警',
    content: '⚠️ 系统告警\n\n告警类型: [告警类型]\n告警内容: [告警内容]\n触发时间: [时间]\n\n请及时处理',
  },
  {
    title: '每日报告',
    content: '📊 每日运行报告\n\n今日任务: 15\n成功: 13\n失败: 2\n成功率: 86.7%\n\n详情请查看控制台',
  },
]

const enabledChannels = computed(() => {
  return channels.value.filter(c => c.enabled)
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

const loadChannels = async () => {
  try {
    const result = await notificationApi.getChannels()
    channels.value = result.channels || []
  } catch (e) {
    console.error('加载渠道失败:', e)
  }
}

const loadRecentLogs = async () => {
  try {
    const result = await notificationApi.getLogs({ limit: 5 })
    recentLogs.value = result.logs || []
  } catch (e) {
    console.error('加载日志失败:', e)
  }
}

const useTemplate = (template: { title: string; content: string }) => {
  form.value.title = template.title
  form.value.content = template.content
}

const sendNotification = async () => {
  if (!form.value.channel) {
    ElMessage.warning('请选择通知渠道')
    return
  }
  if (!form.value.title) {
    ElMessage.warning('请输入通知标题')
    return
  }
  if (!form.value.content) {
    ElMessage.warning('请输入通知内容')
    return
  }

  sending.value = true
  try {
    await notificationApi.send({
      channel: form.value.channel,
      title: form.value.title,
      content: form.value.content,
    })
    ElMessage.success('发送成功')
    resetForm()
    await loadRecentLogs()
  } catch (e) {
    console.error('发送失败:', e)
    ElMessage.error('发送失败')
  } finally {
    sending.value = false
  }
}

const resetForm = () => {
  form.value = {
    channel: '',
    title: '',
    content: '',
  }
}

onMounted(() => {
  loadChannels()
  loadRecentLogs()
})
</script>

<style scoped>
.send-notification {
  padding: 20px;
}

.templates {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 15px;
}

.template-card {
  cursor: pointer;
  transition: all 0.3s;
}

.template-card:hover {
  transform: translateY(-4px);
}

.template-card h4 {
  margin: 0 0 10px 0;
  font-size: 16px;
}

.template-card p {
  margin: 0;
  color: #666;
  font-size: 14px;
}
</style>
