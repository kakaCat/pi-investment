import client from '@/utils/request'

export const memoryApi = {
  list: (params?: { category?: string; tag?: string; limit?: number }) =>
    client.get('/memory', { params }),
  search: (q: string) => client.get('/memory/search', { params: { q } }),
  getTags: () => client.get('/memory/tags'),
  createTag: (name: string) => client.post('/memory/tags', { name }),
  deleteTag: (name: string) => client.delete(`/memory/tags/${name}`),
}
