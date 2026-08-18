const isDev = import.meta.env.DEV

/**
 * 日志工具类
 * 开发环境显示所有日志，生产环境只显示错误
 */
export const logger = {
  /**
   * 普通日志
   */
  log: (...args: any[]) => {
    if (isDev) {
      console.log('[LOG]', new Date().toLocaleTimeString(), ...args)
    }
  },

  /**
   * 警告日志
   */
  warn: (...args: any[]) => {
    if (isDev) {
      console.warn('[WARN]', new Date().toLocaleTimeString(), ...args)
    }
  },

  /**
   * 错误日志（生产环境也会显示）
   */
  error: (...args: any[]) => {
    console.error('[ERROR]', new Date().toLocaleTimeString(), ...args)
    // TODO: 发送到错误监控服务（如 Sentry）
  },

  /**
   * 调试日志
   */
  debug: (...args: any[]) => {
    if (isDev) {
      console.debug('[DEBUG]', new Date().toLocaleTimeString(), ...args)
    }
  },

  /**
   * 信息日志
   */
  info: (...args: any[]) => {
    if (isDev) {
      console.info('[INFO]', new Date().toLocaleTimeString(), ...args)
    }
  },
}

export default logger
