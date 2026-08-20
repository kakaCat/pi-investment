import client from '@/utils/request'

export const profileApi = {
  // 获取用户配置
  getProfile: () => client.get('/profile'),

  // 更新用户配置
  updateProfile: (data: {
    email?: string
    display_name?: string
    bio?: string
    preferences?: any
  }) => client.put('/profile', data),

  // 获取 API 密钥列表
  getAPIKeys: () => client.get('/profile/api-keys'),

  // 获取活动日志
  getActivityLogs: (params?: { limit?: number }) =>
    client.get('/profile/activity', { params }),
}
