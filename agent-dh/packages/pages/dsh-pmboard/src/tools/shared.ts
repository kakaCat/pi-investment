/**
 * 工具壳共享（REQ-47939a t8）——工具壳的通用渲染助手。
 * @module dsh-pmboard/tools/shared
 */
export const renderJson = (_args: unknown, value: unknown) => [
  { type: 'text', text: JSON.stringify(value, null, 2) },
]
