import client from '@/utils/request'

export const decisionApi = {
  list: (params?: { action?: string; status?: string; limit?: number }) =>
    client.get('/decisions', { params }),
  get: (id: string) => client.get(`/decisions/${id}`),
  getStatistics: () => client.get('/decisions/statistics'),
}
