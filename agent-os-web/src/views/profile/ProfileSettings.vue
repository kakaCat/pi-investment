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
              <el-input v-model="profile.username" disabled />
            </el-form-item>
            <el-form-item label="显示名称">
              <el-input v-model="profile.display_name" placeholder="输入显示名称" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="profile.email" />
            </el-form-item>
            <el-form-item label="简介">
              <el-input v-model="profile.bio" type="textarea" :rows="3" placeholder="个人简介" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="saveProfile">保存</el-button>
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
              <el-button type="primary" :loading="saving" @click="saveSettings">保存</el-button>
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

      <el-table :data="apiKeys" v-loading="keysLoading" stripe>
        <el-table-column prop="name" label="名称" width="180" />
        <el-table-column prop="key_prefix" label="前缀" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.key_prefix }}***</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="permissions" label="权限" width="180">
          <template #default="{ row }">
            <el-tag v-for="p in row.permissions" :key="p" size="small" type="info" effect="plain" style="margin-right: 4px">
              {{ p }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="expires_at" label="过期时间" width="200">
          <template #default="{ row }">
            {{ row.expires_at ? formatTime(row.expires_at) : '永久' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="200">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!keysLoading && apiKeys.length === 0" description="暂无 API 密钥" />
    </el-card>

    <!-- 账户操作 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>账户操作</span>
      </template>
      <el-space direction="vertical" size="large">
        <div>
          <el-button @click="showChangePasswordDialog = true">修改密码</el-button>
          <el-text type="info" style="margin-left: 10px">后端暂未提供修改密码接口</el-text>
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
import { ElMessage } from 'element-plus'
import { profileApi } from '@/api/profile'
import { useAppStore } from '@/stores/app'
import { formatTime } from '@/utils/format'

const appStore = useAppStore()

const profile = ref({
  username: '',
  display_name: '',
  email: '',
  bio: '',
})

const settings = ref({
  theme: appStore.theme,
  language: appStore.language,
  pageSize: appStore.pageSize,
  autoRefresh: appStore.autoRefresh,
  refreshInterval: appStore.refreshInterval,
})

const saving = ref(false)
const apiKeys = ref<any[]>([])
const keysLoading = ref(false)
const showChangePasswordDialog = ref(false)
const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const loadProfile = async () => {
  try {
    const data = await profileApi.getProfile()
    profile.value = {
      username: data.username || 'admin',
      display_name: data.display_name || '',
      email: data.email || '',
      bio: data.bio || '',
    }
    // 同步偏好设置
    if (data.preferences) {
      settings.value.theme = data.preferences.theme || appStore.theme
      settings.value.language = data.preferences.language || appStore.language
    }
  } catch (e) {
    console.error('加载个人资料失败:', e)
    ElMessage.error('加载个人资料失败')
  }
}

const loadAPIKeys = async () => {
  keysLoading.value = true
  try {
    const data = await profileApi.getAPIKeys()
    apiKeys.value = data.keys || []
  } catch (e) {
    console.error('加载 API 密钥失败:', e)
    ElMessage.error('加载 API 密钥失败')
  } finally {
    keysLoading.value = false
  }
}

const saveProfile = async () => {
  saving.value = true
  try {
    await profileApi.updateProfile({
      email: profile.value.email || undefined,
      display_name: profile.value.display_name || undefined,
      bio: profile.value.bio || undefined,
    })
    ElMessage.success('基本信息已保存')
  } catch (e) {
    console.error('保存基本信息失败:', e)
    ElMessage.error('保存基本信息失败')
  } finally {
    saving.value = false
  }
}

const saveSettings = async () => {
  saving.value = true
  try {
    // 更新到 store
    appStore.theme = settings.value.theme
    appStore.language = settings.value.language
    appStore.pageSize = settings.value.pageSize
    appStore.autoRefresh = settings.value.autoRefresh
    appStore.refreshInterval = settings.value.refreshInterval

    // 持久化到后端 preferences
    await profileApi.updateProfile({
      preferences: {
        theme: settings.value.theme,
        language: settings.value.language,
        notifications: true,
      },
    })
    ElMessage.success('界面设置已保存')
  } catch (e) {
    console.error('保存界面设置失败:', e)
    ElMessage.error('保存界面设置失败')
  } finally {
    saving.value = false
  }
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

  ElMessage.info('后端暂未提供修改密码接口')
  showChangePasswordDialog.value = false
}

const logout = () => {
  ElMessage.success('已退出登录')
  // TODO: 清除登录状态并跳转到登录页（暂无登录系统）
}

onMounted(() => {
  changeTheme(settings.value.theme)
  loadProfile()
  loadAPIKeys()
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
</style>
