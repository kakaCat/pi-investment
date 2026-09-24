/**
 * 模板根解析（REQ-260922213356-4a45 T-3 / design S-5）。
 *
 * 唯一允许 import node:path 的模板相关模块（组合根/适配层）；domain 不碰环境与磁盘。
 * 解析优先级：配置 templateRoot（必须是绝对路径）> 包根下 templates（源码态 src/index.ts 与
 * 构建态 dist/index.mjs 同解为 <pkg>/templates）。解析不出/配置非法 → undefined（调用方响亮留痕）。
 *
 * @module dsh-pmboard/adapters/TemplateRoot
 */
import { isAbsolute, resolve } from 'node:path'

export interface TemplateAddressConfig {
  /** 模板根绝对路径（可覆盖包根解析，便于 worktree / 多实例部署）。 */
  readonly templateRoot?: string
  /** 地址段开关（默认 true；false = 完全回退到改造前注入行为）。 */
  readonly addressSectionEnabled?: boolean
}

/** 配置优先；否则按模块位置解析包根 templates。非绝对/空 → undefined。 */
export function resolveTemplateRoot(config: TemplateAddressConfig | undefined, moduleDir: string): string | undefined {
  const configured = config?.templateRoot?.trim()
  if (configured !== undefined && configured.length > 0) {
    return isAbsolute(configured) ? configured : undefined
  }
  return resolve(moduleDir, '..', 'templates')
}

/** 地址段是否启用（显式 false 关闭；缺省 = 启用）。 */
export function addressSectionEnabled(config: TemplateAddressConfig | undefined): boolean {
  return config?.addressSectionEnabled !== false
}

/** 注入侧配置投影（组合根一行调用即可）。 */
export interface AddressInjection {
  readonly templateRoot?: string
  readonly enabled: boolean
}

/** 解析模板根 + 开关；开关开但解析失败时经 warn 响亮留痕（address_section_disabled）。 */
export function resolveAddressInjection(
  config: TemplateAddressConfig | undefined,
  moduleDir: string,
  warn?: (message: string) => void,
): AddressInjection {
  const templateRoot = resolveTemplateRoot(config, moduleDir)
  const enabled = addressSectionEnabled(config)
  if (enabled && templateRoot === undefined) {
    warn?.('reqboard 地址段未启用：templateRoot 解析失败（address_section_disabled）')
  }
  return { ...(templateRoot === undefined ? {} : { templateRoot }), enabled }
}
