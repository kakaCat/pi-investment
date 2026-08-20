import client from '@/utils/request'

export const notificationApi = {
  getChannels: () => client.get('/notifications/channels'),
  createChannel: (data: {
    code: string
    name: string
    description?: string
    enabled?: boolean
    config?: any
  }) => client.post('/notifications/channels', data),
  deleteChannel: (id: string) => client.delete(`/notifications/channels/${id}`),
  getLogs: (params?: { limit?: number }) => client.get('/notifications/logs', { params }),
  send: (data: { channel: string; title: string; content: string }) =>
    client.post('/notifications/send', data),
  getProviders: () => client.get('/notifications/providers'),
}
