import axios, { AxiosError } from 'axios'
import type { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '@/types/models'
import { performanceMonitor } from '@/utils/performance'

// 扩展 Axios 配置以支持性能监控
interface CustomAxiosRequestConfig extends InternalAxiosRequestConfig {
  _startTime?: number
  /** 为 true 时拦截器不弹全局错误提示，由调用方自行处理（用于非关键可选请求） */
  silent?: boolean
}

// 调用方可传的扩展选项（会透传进 axios config）
export interface ApiRequestOptions extends AxiosRequestConfig {
  /** 为 true 时拦截器不弹全局错误提示，由调用方自行处理（用于非关键可选请求） */
  silent?: boolean
}

class ApiClient {
  private instance: AxiosInstance

  constructor(baseURL: string) {
    this.instance = axios.create({
      baseURL,
      timeout: import.meta.env.VITE_API_TIMEOUT || 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    // 请求拦截器
    this.instance.interceptors.request.use(
      (config: CustomAxiosRequestConfig) => {
        // 记录请求开始时间
        config._startTime = Date.now()

        // 可以在这里添加token
        // const token = localStorage.getItem('token')
        // if (token) {
        //   config.headers.Authorization = `Bearer ${token}`
        // }
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // 响应拦截器
    this.instance.interceptors.response.use(
      (response) => {
        // 记录 API 性能
        const config = response.config as CustomAxiosRequestConfig
        if (config._startTime && import.meta.env.VITE_ENABLE_PERFORMANCE_MONITOR !== 'false') {
          const duration = Date.now() - config._startTime
          performanceMonitor.recordAPICall(
            config.url || '',
            config.method?.toUpperCase() || 'GET',
            duration,
            response.status
          )
        }

        const data = response.data as ApiResponse

        // 如果后端返回的是标准格式 { code, message, data }
        if (data.code !== undefined) {
          if (data.code === 0 || data.code === 200) {
            return data.data
          } else {
            ElMessage.error(data.message || '请求失败')
            return Promise.reject(new Error(data.message))
          }
        }

        // QuantSys V2 返回 { success, data }，前端页面直接消费 data。
        if (
          data &&
          typeof data === 'object' &&
          'success' in data &&
          'data' in data &&
          (data as any).success !== false
        ) {
          return (data as any).data
        }

        if (data && typeof data === 'object' && 'error' in data) {
          const message = String((data as any).error || '请求失败')
          ElMessage.error(message)
          return Promise.reject(new Error(message))
        }

        // 否则直接返回数据
        return response.data
      },
      (error: AxiosError) => {
        // 记录失败的 API 性能
        const config = error.config as CustomAxiosRequestConfig
        if (config?._startTime && import.meta.env.VITE_ENABLE_PERFORMANCE_MONITOR !== 'false') {
          const duration = Date.now() - config._startTime
          performanceMonitor.recordAPICall(
            config.url || '',
            config.method?.toUpperCase() || 'GET',
            duration,
            error.response?.status
          )
        }

        // 调用方声明静默：不弹全局错误提示，直接 reject 交由调用方处理
        if (config?.silent) {
          return Promise.reject(error)
        }

        if (error.response) {
          const { status, data } = error.response

          // 优先使用后端返回的 error 消息
          const backendMsg = (data as any)?.error

          switch (status) {
            case 401:
              ElMessage.error(backendMsg || '未授权，请重新登录')
              break
            case 403:
              ElMessage.error(backendMsg || '没有权限访问')
              break
            case 404:
              ElMessage.error(backendMsg || '请求的资源不存在')
              break
            case 500:
              ElMessage.error(backendMsg || '服务器错误')
              break
            default:
              ElMessage.error(backendMsg || error.message || '请求失败')
          }
        } else if (error.request) {
          ElMessage.error('网络错误，请检查网络连接')
        } else {
          ElMessage.error(error.message || '请求失败')
        }

        return Promise.reject(error)
      }
    )
  }

  public get<T = any>(url: string, config?: ApiRequestOptions): Promise<T> {
    return this.instance.get(url, config)
  }

  public post<T = any>(url: string, data?: any, config?: ApiRequestOptions): Promise<T> {
    return this.instance.post(url, data, config)
  }

  public put<T = any>(url: string, data?: any, config?: ApiRequestOptions): Promise<T> {
    return this.instance.put(url, data, config)
  }

  public delete<T = any>(url: string, config?: ApiRequestOptions): Promise<T> {
    return this.instance.delete(url, config)
  }
}

// 直连 quantsys-v2 Flask 后端 (127.0.0.1:5001)
export const apiClient = new ApiClient(
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5001'
)
