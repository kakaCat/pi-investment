/**
 * 模板地址域出口（REQ-260922213356-4a45 T-2）：注入点与测试只从这里 import。
 * @module dsh-pmboard/domain/template
 */
export * from './types.js'
export { NODE_TEMPLATES } from './registry.js'
export { resolveNodeTemplates, resolveUpstreamDocs, kindTitle } from './resolve.js'
export { renderAddressSection } from './render.js'
