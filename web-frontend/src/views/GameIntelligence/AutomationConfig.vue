<template>
  <div class="automation-config">
    <h1>⚙️ 自动化配置</h1>

    <!-- 定时任务配置 -->
    <el-card class="box-card">
      <template #header>
        <span>🕐 定时任务配置</span>
      </template>

      <div class="task-configs">
        <div v-for="task in tasks" :key="task.id" class="task-config-item">
          <div class="task-header">
            <div class="task-info">
              <h3>{{ task.name }}</h3>
              <p>{{ task.description }}</p>
            </div>
            <el-switch v-model="task.enabled" @change="toggleTask(task)" />
          </div>

          <div class="task-settings">
            <el-form :inline="true" size="small">
              <el-form-item label="执行时间">
                <el-input v-model="task.schedule" :disabled="!task.enabled" style="width: 150px" />
              </el-form-item>
              <el-form-item label="执行周期">
                <el-select v-model="task.period" :disabled="!task.enabled" style="width: 120px">
                  <el-option label="每天" value="daily" />
                  <el-option label="工作日" value="weekday" />
                  <el-option label="周末" value="weekend" />
                </el-select>
              </el-form-item>
            </el-form>
          </div>

          <div class="task-actions">
            <el-button size="small" :disabled="!task.enabled" @click="executeNow(task)">
              立即执行
            </el-button>
            <el-button size="small" type="primary" :disabled="!task.enabled" @click="saveTaskConfig(task)">
              保存配置
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 自动决策规则 -->
    <el-card class="box-card mt-20">
      <template #header>
        <span>🎯 自动决策规则</span>
      </template>

      <div class="decision-rules">
        <el-form label-width="180px">
          <el-form-item>
            <template #label>
              <el-checkbox v-model="rules.autoCreatePool">自动创建池子</el-checkbox>
            </template>
            <div class="rule-detail">
              <p>当发现高置信度博弈机会时，自动创建投资池</p>
              <el-form :inline="true" size="small">
                <el-form-item label="置信度阈值">
                  <el-input-number
                    v-model="rules.autoCreatePoolThreshold"
                    :min="0"
                    :max="100"
                    :disabled="!rules.autoCreatePool"
                  />
                  <span class="unit">%</span>
                </el-form-item>
              </el-form>
            </div>
          </el-form-item>

          <el-form-item>
            <template #label>
              <el-checkbox v-model="rules.autoRiskControl">自动风控</el-checkbox>
            </template>
            <div class="rule-detail">
              <p>当池子评分过低时，自动触发风控措施</p>
              <el-form :inline="true" size="small">
                <el-form-item label="评分阈值">
                  <el-input-number
                    v-model="rules.autoRiskControlThreshold"
                    :min="0"
                    :max="100"
                    :disabled="!rules.autoRiskControl"
                  />
                  <span class="unit">分</span>
                </el-form-item>
                <el-form-item label="风控动作">
                  <el-select v-model="rules.riskControlAction" :disabled="!rules.autoRiskControl">
                    <el-option label="仅发送预警" value="alert" />
                    <el-option label="自动减仓50%" value="reduce_50" />
                    <el-option label="自动清仓" value="clear" />
                  </el-select>
                </el-form-item>
              </el-form>
            </div>
          </el-form-item>

          <el-form-item>
            <template #label>
              <el-checkbox v-model="rules.autoLearning">自动学习</el-checkbox>
            </template>
            <div class="rule-detail">
              <p>从历史决策中自动学习和优化</p>
              <el-form :inline="true" size="small">
                <el-form-item label="评估周期">
                  <el-input-number
                    v-model="rules.learningEvaluationDays"
                    :min="1"
                    :max="30"
                    :disabled="!rules.autoLearning"
                  />
                  <span class="unit">天后</span>
                </el-form-item>
                <el-form-item label="知识提取">
                  <el-select v-model="rules.knowledgeExtraction" :disabled="!rules.autoLearning">
                    <el-option label="仅成功决策" value="success_only" />
                    <el-option label="所有决策" value="all" />
                  </el-select>
                </el-form-item>
              </el-form>
            </div>
          </el-form-item>
        </el-form>

        <div class="form-actions">
          <el-button type="primary" @click="saveRules">保存规则配置</el-button>
          <el-button @click="resetRules">重置为默认</el-button>
        </div>
      </div>
    </el-card>

    <!-- 通知配置 -->
    <el-card class="box-card mt-20">
      <template #header>
        <span>🔔 通知配置</span>
      </template>

      <el-form label-width="120px">
        <el-form-item>
          <template #label>
            <el-checkbox v-model="notification.feishuEnabled">飞书推送</el-checkbox>
          </template>
          <el-input
            v-model="notification.feishuWebhook"
            :disabled="!notification.feishuEnabled"
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
            style="width: 500px"
          />
        </el-form-item>

        <el-form-item label="推送内容" v-if="notification.feishuEnabled">
          <el-checkbox-group v-model="notification.feishuContent">
            <el-checkbox label="critical_alerts">紧急预警</el-checkbox>
            <el-checkbox label="daily_report">每日报告</el-checkbox>
            <el-checkbox label="all_decisions">所有决策</el-checkbox>
            <el-checkbox label="learning_report">学习报告</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item>
          <template #label>
            <el-checkbox v-model="notification.emailEnabled">邮件通知</el-checkbox>
          </template>
          <el-input
            v-model="notification.emailAddress"
            :disabled="!notification.emailEnabled"
            placeholder="your@email.com"
            style="width: 300px"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveNotificationConfig">保存通知配置</el-button>
          <el-button @click="testNotification">发送测试通知</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAutomationConfig,
  saveAutomationConfig as saveAutomationConfigAPI,
  saveNotificationConfigAPI
} from '@/services/game-intelligence'

const tasks = ref([
  {
    id: 1,
    name: '早盘分析 (9:00)',
    description: '对手行为分析 + 预警检查 + 池子评估',
    enabled: true,
    schedule: '09:00',
    period: 'weekday'
  },
  {
    id: 2,
    name: '实时监控 (每5分钟)',
    description: '检查紧急预警',
    enabled: true,
    schedule: '*/5 9-15 * * 1-5',
    period: 'weekday'
  },
  {
    id: 3,
    name: '每日学习 (18:00)',
    description: '评估历史决策 + 提取知识 + 学习优化',
    enabled: true,
    schedule: '18:00',
    period: 'daily'
  }
])

const rules = ref({
  autoCreatePool: false,
  autoCreatePoolThreshold: 85,
  autoRiskControl: true,
  autoRiskControlThreshold: 40,
  riskControlAction: 'alert',
  autoLearning: true,
  learningEvaluationDays: 7,
  knowledgeExtraction: 'success_only'
})

const notification = ref({
  feishuEnabled: false,
  feishuWebhook: '',
  feishuContent: ['critical_alerts', 'daily_report'],
  emailEnabled: false,
  emailAddress: ''
})

const toggleTask = (task: any) => {
  ElMessage.success(`${task.name} 已${task.enabled ? '启用' : '禁用'}`)
}

const executeNow = (task: any) => {
  ElMessage.info(`正在执行 ${task.name}...`)
  // TODO: 调用API立即执行任务
}

const saveTaskConfig = (task: any) => {
  ElMessage.success('任务配置已保存')
  // TODO: 调用API保存配置
}

const saveRules = () => {
  ElMessage.success('规则配置已保存')
  // TODO: 调用API保存规则
}

const resetRules = () => {
  rules.value = {
    autoCreatePool: false,
    autoCreatePoolThreshold: 85,
    autoRiskControl: true,
    autoRiskControlThreshold: 40,
    riskControlAction: 'alert',
    autoLearning: true,
    learningEvaluationDays: 7,
    knowledgeExtraction: 'success_only'
  }
  ElMessage.success('已重置为默认配置')
}

const saveNotificationConfig = async () => {
  try {
    const res = await saveNotificationConfigAPI(notification.value)
    if (res.success) {
      ElMessage.success('通知配置已保存')
    } else {
      ElMessage.error('保存失败: ' + res.error)
    }
  } catch (error) {
    console.error('保存通知配置失败:', error)
    ElMessage.error('保存失败，请检查网络连接')
  }
}

const testNotification = () => {
  ElMessage.info('正在发送测试通知...')
  // TODO: 调用API发送测试通知
}

// 加载配置
const loadConfig = async () => {
  try {
    const res = await getAutomationConfig()
    if (res.success && res.data) {
      // 加载任务配置
      if (res.data.tasks) {
        // 更新任务配置
        tasks.value = tasks.value.map(task => {
          const key = task.name.includes('早盘') ? 'morning_analysis' :
                     task.name.includes('监控') ? 'realtime_monitor' : 'daily_learning'
          const config = res.data.tasks[key]
          return config ? { ...task, enabled: config.enabled } : task
        })
      }

      // 加载规则配置
      if (res.data.rules) {
        rules.value = {
          autoCreatePool: res.data.rules.auto_create_pool,
          autoCreatePoolThreshold: res.data.rules.auto_create_pool_threshold,
          autoRiskControl: res.data.rules.auto_risk_control,
          autoRiskControlThreshold: res.data.rules.auto_risk_control_threshold,
          riskControlAction: res.data.rules.risk_control_action,
          autoLearning: res.data.rules.auto_learning,
          learningEvaluationDays: res.data.rules.learning_evaluation_days,
          knowledgeExtraction: res.data.rules.knowledge_extraction
        }
      }

      // 加载通知配置
      if (res.data.notification) {
        notification.value = {
          feishuEnabled: res.data.notification.feishu_enabled,
          feishuWebhook: res.data.notification.feishu_webhook,
          feishuContent: res.data.notification.feishu_content,
          emailEnabled: res.data.notification.email_enabled,
          emailAddress: res.data.notification.email_address
        }
      }
    }
  } catch (error) {
    console.error('加载配置失败:', error)
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.automation-config {
  padding: 20px;
}

.task-configs {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.task-config-item {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 20px;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 15px;
}

.task-info h3 {
  margin: 0 0 5px 0;
  font-size: 16px;
}

.task-info p {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.task-settings {
  margin-bottom: 15px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.task-actions {
  display: flex;
  gap: 10px;
}

.decision-rules {
  padding: 20px 0;
}

.rule-detail {
  padding-left: 20px;
}

.rule-detail p {
  color: #606266;
  margin: 0 0 10px 0;
  font-size: 14px;
}

.rule-detail .unit {
  margin-left: 5px;
  color: #909399;
}

.form-actions {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
  display: flex;
  gap: 10px;
}

.mt-20 {
  margin-top: 20px;
}
</style>
