import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User, UserSettings } from '@/types'

export const useUserStore = defineStore('user', () => {
  // State
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const settings = ref<UserSettings>({
    theme: 'light',
    language: 'zh-CN',
    notifications: {
      signal: true,
      order: true,
      risk: true,
      agent: true
    },
    trading: {
      defaultQuantity: 100,
      confirmBeforeOrder: true,
      autoApproveSignals: false
    }
  })
  const isAuthenticated = ref(false)

  // Actions
  const login = async (_username: string, _password: string) => {
    try {
      // TODO: 调用登录API
      // const response = await authApi.login(_username, _password)
      // token.value = response.token
      // user.value = response.user
      isAuthenticated.value = true

      // 保存到localStorage
      localStorage.setItem('auth_token', token.value || '')
      localStorage.setItem('user_info', JSON.stringify(user.value))
    } catch (e: any) {
      throw e
    }
  }

  const logout = () => {
    user.value = null
    token.value = null
    isAuthenticated.value = false

    // 清除localStorage
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_info')
  }

  const updateSettings = (newSettings: Partial<UserSettings>) => {
    settings.value = { ...settings.value, ...newSettings }
    localStorage.setItem('user_settings', JSON.stringify(settings.value))
  }

  const loadFromStorage = () => {
    const savedToken = localStorage.getItem('auth_token')
    const savedUser = localStorage.getItem('user_info')
    const savedSettings = localStorage.getItem('user_settings')

    if (savedToken && savedUser) {
      token.value = savedToken
      user.value = JSON.parse(savedUser)
      isAuthenticated.value = true
    }

    if (savedSettings) {
      settings.value = JSON.parse(savedSettings)
    }
  }

  return {
    // State
    user,
    token,
    settings,
    isAuthenticated,
    // Actions
    login,
    logout,
    updateSettings,
    loadFromStorage
  }
})
