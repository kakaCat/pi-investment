import client from '@/utils/request'

export const systemApi = {
  getStatus: () => client.get('/system/status'),
  getQuotas: () => client.get('/system/quotas'),
  getLogs: (params?: { limit?: number; level?: string }) =>
    client.get('/system/logs', { params }),
  getNamespaces: () => client.get('/system/namespaces'),
  createNamespace: (data: { name: string; description?: string }) =>
    client.post('/system/namespaces', data),
  deleteNamespace: (name: string) =>
    client.delete(`/system/namespaces/${encodeURIComponent(name)}`),
}
