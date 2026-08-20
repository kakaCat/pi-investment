import client from '@/utils/request'

export const eventApi = {
  getHistory: (params?: { type?: string; start?: string; end?: string; limit?: number }) =>
    client.get('/events/history', { params }),
  getAlertRules: () => client.get('/events/alerts'),
  createAlertRule: (data: any) => client.post('/events/alerts', data),
  deleteAlertRule: (id: string) => client.delete(`/events/alerts/${id}`),
  updateAlertRule: (id: string, data: { enabled: boolean }) =>
    client.put(`/events/alerts/${id}`, data),
}
