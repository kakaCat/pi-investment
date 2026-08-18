import client from '@/utils/request'

export const notificationApi = {
  getChannels: () => client.get('/notifications/channels'),
  getLogs: (params?: { limit?: number }) => client.get('/notifications/logs', { params }),
  send: (data: { channel: string; title: string; content: string }) =>
    client.post('/notifications/send', data),
  getProviders: () => client.get('/notifications/providers'),
}
