<template>
  <div class="profile-settings">
    <el-row :gutter="20">
      <!-- 基本信息 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>基本信息</span>
          </template>
          <el-form :model="profile" label-width="100px">
            <el-form-item label="用户名">
              <el-input v-model="profile.username" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="profile.email" />
            </el-form-item>
            <el-form-item label="角色">
              <el-tag>{{ profile.role }}</el-tag>
            </el-form-item>
            <el-form-item label="时区">
              <el-select v-model="profile.timezone" placeholder="选择时区">
                <el-option label="Asia/Shanghai (UTC+8)" value="Asia/Shanghai" />
                <el-option label="America/New_York (UTC-5)" value="America/New_York" />
                <el-option label="Europe/London (UTC+0)" value="Europe/London" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveProfile">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 界面设置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>界面设置</span>
          </template>
          <el-form :model="settings" label-width="120px">
            <el-form-item label="主题">
              <el-radio-group v-model="settings.theme" @change="changeTheme">
                <el-radio label="light">浅色</el-radio>
                <el-radio label="dark">深色</el-radio>
                <el-radio label="auto">跟随系统</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="语言">
              <el-select v-model="settings.language">
                <el-option label="简体中文" value="zh-CN" />
                <el-option label="English" value="en-US" />
              </el-select>
            </el-form-item>
            <el-form-item label="每页显示条数">
              <el-input-number v-model="settings.pageSize" :min="10" :max="100" :step="10" />
            </el-form-item>
            <el-form-item label="自动刷新">
              <el-switch v-model="settings.autoRefresh" />
              <span v-if="settings.autoRefresh" style="margin-left: 10px">
                间隔：
                <el-input-number
                  v-model="settings.refreshInterval"
                  :min="10"
                  :max="300"
                  :step="10"
                  size="small"
                  style="width: 120px"
                />
                秒
              </span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveSettings">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- API 密钥 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="header">
          <span>API 密钥</span>
          <el-button type="primary" size="small" @click="generateApiKey">
            <el-icon><Refresh /></el-icon>
            重新生成
          </el-button>
        </div>
      </template>

      <el-alert
        title="提示"
        type="warning"
        :closable="false"
        style="margin-bottom: 20px"
      >
        API 密钥用于调用 Agent OS API，请妥善保管，不要泄露给他人
      </el-alert>

      <div class="api-key-section">
        <el-input
          v-model="apiKey"
          readonly
          :type="showApiKey ? 'text' : 'password'"
          style="width: 400px"
        >
          <template #append>
            <el-button @click="showApiKey = !showApiKey">
              <el-icon><View v-if="!showApiKey" /><Hide v-else /></el-icon>
            </el-button>
            <el-button @click="copyApiKey">
              <el-icon><CopyDocument /></el-icon>
            </el-button>
          </template>
        </el-input>
        <el-button
          type="danger"
          plain
          style="margin-left: 10px"
          @click="revokeApiKey"
        >
          撤销密钥
        </el-button>
      </div>

      <div style="margin-top: 20px">
        <el-text type="info">创建时间: {{ apiKeyCreatedAt }}</el-text>
      </div>
    </el-card>

    <!-- 账户操作 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>账户操作</span>
      </template>
      <el-space direction="vertical" size="large">
        <div>
          <el-button @click="showChangePasswordDialog = true">修改密码</el-button>
        </div>
        <div>
          <el-button type="danger" plain @click="logout">退出登录</el-button>
        </div>
      </el-space>
    </el-card>

    <!-- 修改密码对话框 -->
    <el-dialog v-model="showChangePasswordDialog" title="修改密码" width="400px">
      <el-form :model="passwordForm" label-width="100px">
        <el-form-item label="当前密码">
          <el-input v-model="passwordForm.oldPassword" type="password" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.newPassword" type="password" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="passwordForm.confirmPassword" type="password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showChangePasswordDialog = false">取消</el-button>
        <el-button type="primary" @click="changePassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, View, Hide, CopyDocument } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const profile = ref({
  username: 'admin',
  email: 'admin@example.com',
  role: 'Administrator',
  timezone: 'Asia/Shanghai',
})

const settings = ref({
  theme: appStore.theme,
  language: appStore.language,
  pageSize: appStore.pageSize,
  autoRefresh: appStore.autoRefresh,
  refreshInterval: appStore.refreshInterval,
})

const apiKey = ref('ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
const apiKeyCreatedAt = ref('2024-01-01 10:00:00')
const showApiKey = ref(false)
const showChangePasswordDialog = ref(false)
const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const saveProfile = () => {
  ElMessage.success('基本信息已保存')
}

const saveSettings = () => {
  // 更新到 store
  appStore.theme = settings.value.theme
  appStore.language = settings.value.language
  appStore.pageSize = settings.value.pageSize
  appStore.autoRefresh = settings.value.autoRefresh
  appStore.refreshInterval = settings.value.refreshInterval
  
  ElMessage.success('界面设置已保存')
}

const changeTheme = (theme: string) => {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else if (theme === 'light') {
    document.documentElement.classList.remove('dark')
  } else {
    // auto: 根据系统设置
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (prefersDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }
}

const generateApiKey = async () => {
  try {
    await ElMessageBox.confirm(
      '重新生成 API 密钥将使旧密钥失效，确定继续吗？',
      '确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    // TODO: 调用后端 API
    apiKey.value = 'ak_' + Math.random().toString(36).substring(2, 34)
    apiKeyCreatedAt.value = new Date().toLocaleString('zh-CN')
    ElMessage.success('API 密钥已重新生成')
  } catch {
    // 用户取消
  }
}

const copyApiKey = () => {
  navigator.clipboard.writeText(apiKey.value)
  ElMessage.success('已复制到剪贴板')
}

const revokeApiKey = async () => {
  try {
    await ElMessageBox.confirm(
      '撤销 API 密钥后，使用该密钥的所有请求将失效，确定继续吗？',
      '确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    // TODO: 调用后端 API
    apiKey.value = ''
    ElMessage.success('API 密钥已撤销')
  } catch {
    // 用户取消
  }
}

const changePassword = () => {
  if (!passwordForm.value.oldPassword) {
    ElMessage.warning('请输入当前密码')
    return
  }
  if (!passwordForm.value.newPassword) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  
  // TODO: 调用后端 API
  ElMessage.success('密码修改成功')
  showChangePasswordDialog.value = false
  passwordForm.value = {
    oldPassword: '',
    newPassword: '',
    confirmPassword: '',
  }
}

const logout = () => {
  ElMessage.success('已退出登录')
  // TODO: 清除登录状态并跳转到登录页
}

onMounted(() => {
  changeTheme(settings.value.theme)
})
</script>

<style scoped>
.profile-settings {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.api-key-section {
  display: flex;
  align-items: center;
}
</style>
