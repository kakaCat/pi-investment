import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  // UI 状态
  const sidebarCollapsed = ref(false)
  const theme = ref<'light' | 'dark' | 'auto'>('light')
  const language = ref('zh-CN')
  const pageSize = ref(20)
  const autoRefresh = ref(true)
  const refreshInterval = ref(30)
  
  // 侧边栏控制
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }
  
  // 从 localStorage 加载设置
  function loadSettings() {
    const saved = localStorage.getItem('app-settings')
    if (saved) {
      try {
        const settings = JSON.parse(saved)
        theme.value = settings.theme || 'light'
        language.value = settings.language || 'zh-CN'
        pageSize.value = settings.pageSize || 20
        autoRefresh.value = settings.autoRefresh !== false
        refreshInterval.value = settings.refreshInterval || 30
      } catch (e) {
        console.error('加载设置失败:', e)
      }
    }
  }
  
  // 保存设置到 localStorage
  function saveSettings() {
    const settings = {
      theme: theme.value,
      language: language.value,
      pageSize: pageSize.value,
      autoRefresh: autoRefresh.value,
      refreshInterval: refreshInterval.value,
    }
    localStorage.setItem('app-settings', JSON.stringify(settings))
  }
  
  return {
    // 状态
    sidebarCollapsed,
    theme,
    language,
    pageSize,
    autoRefresh,
    refreshInterval,
    // 方法
    toggleSidebar,
    loadSettings,
    saveSettings,
  }
})
