import client from '@/utils/request'

export const systemApi = {
  getStatus: () => client.get('/system/status'),
  getQuotas: () => client.get('/system/quotas'),
  getLogs: (params?: { limit?: number; level?: string }) =>
    client.get('/system/logs', { params }),
  getNamespaces: () => client.get('/system/namespaces'),
}
