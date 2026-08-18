import client from '@/utils/request'

export const skillApi = {
  list: (params?: any) => client.get('/skills', { params }),
  get: (id: string) => client.get(`/skills/${id}`),
  create: (data: any) => client.post('/skills', data),
  update: (id: string, data: any) => client.put(`/skills/${id}`, data),
  delete: (id: string) => client.delete(`/skills/${id}`),
}
