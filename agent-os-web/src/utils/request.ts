import axios, { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import logger from './logger'
import type { ApiResponse } from '@/types/api'

const client = axios.create({
  // 开发环境用相对路径（走 vite proxy），生产环境用完整 URL
  baseURL: import.meta.env.DEV ? '/api/v1' : (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080/api/v1'),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
client.interceptors.request.use(
  (config) => {
    // 可以在这里添加 token
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    logger.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
client.interceptors.response.use(
  (response) => {
    const data = response.data as ApiResponse

    // 统一处理业务错误
    if (data.success === false) {
      const message = data.message || data.error || '请求失败'
      ElMessage.error(message)
      logger.error('业务错误:', message)
      return Promise.reject(new Error(message))
    }

    // 返回数据部分，如果没有则返回整个响应
    return data.data !== undefined ? data.data : data
  },
  (error: AxiosError) => {
    // 网络错误
    if (!error.response) {
      ElMessage.error('网络错误，请检查网络连接')
      logger.error('网络错误:', error.message)
      return Promise.reject(error)
    }

    // HTTP 错误
    const { status, data } = error.response
    const message = (data as any)?.message || (data as any)?.error || '请求失败'

    switch (status) {
      case 400:
        ElMessage.error(message || '请求参数错误')
        break
      case 401:
        ElMessage.error('未授权，请登录')
        // TODO: 跳转到登录页
        // router.push('/login')
        break
      case 403:
        ElMessage.error('无权限访问')
        break
      case 404:
        ElMessage.error('资源不存在')
        break
      case 500:
        ElMessage.error('服务器错误')
        break
      case 502:
        ElMessage.error('网关错误')
        break
      case 503:
        ElMessage.error('服务暂时不可用')
        break
      case 504:
        ElMessage.error('网关超时')
        break
      default:
        ElMessage.error(message)
    }

    logger.error(`HTTP ${status} 错误:`, message, error.response.data)
    return Promise.reject(error)
  }
)

export default client
