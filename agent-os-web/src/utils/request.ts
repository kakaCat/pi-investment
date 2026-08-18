import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080/api/v1',
  timeout: 30000,
})

client.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.message || err.message
    console.error('API Error:', msg)
    return Promise.reject(err)
  }
)

export default client
