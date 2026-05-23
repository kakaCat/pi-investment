import { ref, reactive } from 'vue'
import type { FormRules } from '@/types'

/**
 * 表单组合式函数
 */
export function useForm<T extends Record<string, any>>(
  initialValues: T,
  _rules?: FormRules
) {
  const formRef = ref()
  const formData = reactive<T>({ ...initialValues })
  const loading = ref(false)
  const errors = ref<Record<string, string>>({})

  // 重置表单
  const reset = () => {
    Object.assign(formData, initialValues)
    errors.value = {}
    formRef.value?.clearValidate()
  }

  // 验证表单
  const validate = async (): Promise<boolean> => {
    if (!formRef.value) return false

    try {
      await formRef.value.validate()
      return true
    } catch (error) {
      return false
    }
  }

  // 验证单个字段
  const validateField = async (field: keyof T): Promise<boolean> => {
    if (!formRef.value) return false

    try {
      await formRef.value.validateField(field as string)
      return true
    } catch (error) {
      return false
    }
  }

  // 清除验证
  const clearValidate = (fields?: (keyof T)[]) => {
    if (!formRef.value) return

    if (fields) {
      formRef.value.clearValidate(fields as string[])
    } else {
      formRef.value.clearValidate()
    }
  }

  // 设置字段值
  const setFieldValue = (field: keyof T, value: any) => {
    (formData as any)[field] = value
  }

  // 设置多个字段值
  const setFieldsValue = (values: Partial<T>) => {
    Object.assign(formData, values)
  }

  // 获取字段值
  const getFieldValue = (field: keyof T) => {
    return (formData as any)[field]
  }

  // 获取所有字段值
  const getFieldsValue = (): T => {
    return { ...formData } as T
  }

  // 提交表单
  const submit = async (
    onSubmit: (values: T) => Promise<void> | void
  ): Promise<boolean> => {
    const isValid = await validate()
    if (!isValid) return false

    loading.value = true
    try {
      await onSubmit(getFieldsValue())
      return true
    } catch (error: any) {
      console.error('Form submit error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    formRef,
    formData,
    loading,
    errors,
    reset,
    validate,
    validateField,
    clearValidate,
    setFieldValue,
    setFieldsValue,
    getFieldValue,
    getFieldsValue,
    submit
  }
}
