import { REGEX } from './constants'

// ========== 表单验证 ==========

/**
 * 验证邮箱
 */
export function validateEmail(email: string): boolean {
  return REGEX.EMAIL.test(email)
}

/**
 * 验证手机号
 */
export function validatePhone(phone: string): boolean {
  return REGEX.PHONE.test(phone)
}

/**
 * 验证股票代码
 */
export function validateStockCode(code: string): boolean {
  return REGEX.STOCK_CODE.test(code)
}

/**
 * 验证密码强度
 */
export function validatePassword(password: string): boolean {
  return REGEX.PASSWORD.test(password)
}

/**
 * 验证必填项
 */
export function validateRequired(value: any): boolean {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.length > 0
  return true
}

/**
 * 验证数字范围
 */
export function validateRange(value: number, min: number, max: number): boolean {
  return value >= min && value <= max
}

/**
 * 验证字符串长度
 */
export function validateLength(value: string, min: number, max: number): boolean {
  const length = value.trim().length
  return length >= min && length <= max
}

// ========== Element Plus 表单验证规则 ==========

/**
 * 必填验证规则
 */
export const requiredRule = (message = '此项为必填项') => ({
  required: true,
  message,
  trigger: 'blur'
})

/**
 * 邮箱验证规则
 */
export const emailRule = {
  validator: (_rule: any, value: string, callback: any) => {
    if (!value) {
      callback()
    } else if (!validateEmail(value)) {
      callback(new Error('请输入正确的邮箱地址'))
    } else {
      callback()
    }
  },
  trigger: 'blur'
}

/**
 * 手机号验证规则
 */
export const phoneRule = {
  validator: (_rule: any, value: string, callback: any) => {
    if (!value) {
      callback()
    } else if (!validatePhone(value)) {
      callback(new Error('请输入正确的手机号'))
    } else {
      callback()
    }
  },
  trigger: 'blur'
}

/**
 * 股票代码验证规则
 */
export const stockCodeRule = {
  validator: (_rule: any, value: string, callback: any) => {
    if (!value) {
      callback()
    } else if (!validateStockCode(value)) {
      callback(new Error('请输入6位数字股票代码'))
    } else {
      callback()
    }
  },
  trigger: 'blur'
}

/**
 * 密码验证规则
 */
export const passwordRule = {
  validator: (_rule: any, value: string, callback: any) => {
    if (!value) {
      callback()
    } else if (!validatePassword(value)) {
      callback(new Error('密码至少8位，包含大小写字母和数字'))
    } else {
      callback()
    }
  },
  trigger: 'blur'
}

/**
 * 数字范围验证规则
 */
export const rangeRule = (min: number, max: number, message?: string) => ({
  validator: (_rule: any, value: number, callback: any) => {
    if (value === null || value === undefined) {
      callback()
    } else if (!validateRange(value, min, max)) {
      callback(new Error(message || `请输入${min}到${max}之间的数字`))
    } else {
      callback()
    }
  },
  trigger: 'blur'
})

/**
 * 字符串长度验证规则
 */
export const lengthRule = (min: number, max: number, message?: string) => ({
  validator: (_rule: any, value: string, callback: any) => {
    if (!value) {
      callback()
    } else if (!validateLength(value, min, max)) {
      callback(new Error(message || `长度应在${min}到${max}个字符之间`))
    } else {
      callback()
    }
  },
  trigger: 'blur'
})

/**
 * 确认密码验证规则
 */
export const confirmPasswordRule = (passwordField: string) => ({
  validator: (_rule: any, value: string, callback: any, form: any) => {
    if (!value) {
      callback()
    } else if (value !== form[passwordField]) {
      callback(new Error('两次输入的密码不一致'))
    } else {
      callback()
    }
  },
  trigger: 'blur'
})
