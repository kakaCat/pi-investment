/**
 * 右栏 tab 挂载助手 —— 把纯 DOM 看板注册成 DSH 原生右侧栏（sidebarRight）的一个 tab。
 *
 * 为什么：这些看板原本用 createBoardShell 把容器挂进中心会话列（html[data-*-active]
 * 隐藏会话列其它子元素），点击入口 = 整页换成看板。用户要求改为「在右侧框里打开」，
 * 即与会话并排的右侧面板。DSH 官方右栏的公开扩展路径是两阶段注册：
 *   ① ctx.sidebarRightTabs.register({ id, kind, title })  —— 类型（静态声明）
 *   ② ctx.slots.register({ name: 'sidebar.right.pane.tab', key: id }, Body) —— 正文（React）
 * 然后 ctx.sidebarRight.openTab(kind) 打开。
 *
 * 正文是 React 组件（slot 体系要求），但看板仍是纯 DOM：组件只渲染一个宿主 div，
 * 在 useEffect 里把页面的 DOM 树挂进去，卸载时交给页面清理。react 由 shell 提供
 * （client bundle 里 external，不打包副本）。
 *
 * 注册失败（服务未就绪 / 无会话）由调用方决定降级路径；本模块只负责「如实报错」，
 * 不静默吞掉 —— 静默失败会让用户以为看板坏了。
 *
 * @module page-kit/client/right-tab
 */
import { createElement, useEffect, useRef } from 'react'

/** 右栏 tab 宿主样式（一次性注入，避免依赖各页面样式表）。 */
export const RIGHT_TAB_HOST_CLASS = 'dsh-right-tab-host'
const HOST_STYLE_ID = 'dsh-right-tab-host-style'
const HOST_STYLES = `
.${RIGHT_TAB_HOST_CLASS}{display:flex;flex-direction:column;height:100%;min-height:0;overflow:hidden}
.${RIGHT_TAB_HOST_CLASS}>*{min-height:0}
.${RIGHT_TAB_HOST_CLASS} .dsh-right-tab-error{padding:16px 18px;color:#b94a48;font:13px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
`

export interface RightTabOptions {
  /** tab 实现身份（全局唯一，通常用包名） */
  id: string
  /** 页面类型 discriminator（openTab 时用） */
  kind: string
  /** tab chip 文字（打开时捕获） */
  title: string
  /**
   * 把看板正文挂进容器；返回清理函数（关闭 tab / 插件卸载时调用）。
   * 抛错会被捕获并显示在面板里（不静默）。
   */
  mount(container: HTMLElement): (() => void) | void
}

export interface RightTabHandle {
  /** 打开或聚焦该 tab；返回是否发起成功（false=服务缺失/无会话，调用方应提示） */
  open(): boolean
  /** 已激活时关闭该 tab，否则打开/聚焦 */
  toggle(): void
  /** 若该 tab 是当前激活 tab 则关闭 */
  close(): void
  /** 该 tab 当前是否处于激活且右栏展开 */
  isActive(): boolean
  /** 注销 tab 类型与正文（插件卸载/HMR） */
  dispose(): void
}

/** 客户端 ctx 的最小投影（宽容读取，缺字段即降级）。 */
interface ClientCtxLike {
  sidebarRight?: {
    openTab?: (kind: string, options?: unknown) => void
    close?: (tabId: unknown) => void
    active?: () => { id?: unknown; kind?: unknown } | undefined
    isExpanded?: () => boolean
  }
  sidebarRightTabs?: {
    register?: (definition: unknown) => (() => void) | undefined
  }
  slots?: {
    inject?: (name: string, thunk: () => unknown) => unknown
    register?: (options: unknown, occupant: unknown) => unknown
  }
  effect?: (fn: () => unknown, label?: string) => unknown
}

function injectHostStyles(): void {
  if (typeof document === 'undefined') return
  if (document.getElementById(HOST_STYLE_ID) !== null) return
  const style = document.createElement('style')
  style.id = HOST_STYLE_ID
  style.textContent = HOST_STYLES
  document.head.appendChild(style)
}

/**
 * 构造 tab 正文组件：一个宿主 div + 在 effect 里挂载页面 DOM。
 * @param opts - 注册选项（id 用于调试定位；mount 是页面挂载回调）
 */
function makeBody(opts: RightTabOptions): (props: Record<string, unknown>) => unknown {
  return function RightTabBody(_props: Record<string, unknown>): unknown {
    const hostRef = useRef<HTMLDivElement | null>(null)

    useEffect(() => {
      const host = hostRef.current
      if (host === null) return
      let cleanup: (() => void) | void
      try {
        cleanup = opts.mount(host)
      } catch (error) {
        console.error('[page-kit] 右栏看板挂载失败 ' + opts.id + ':', error)
        const box = document.createElement('div')
        box.className = 'dsh-right-tab-error'
        box.textContent = '看板加载失败：' + (error instanceof Error ? error.message : String(error))
        host.appendChild(box)
      }
      return () => {
        try {
          if (typeof cleanup === 'function') cleanup()
        } catch (error) {
          console.error('[page-kit] 右栏看板卸载清理失败 ' + opts.id + ':', error)
        }
      }
    }, [])

    return createElement('div', {
      ref: hostRef,
      className: RIGHT_TAB_HOST_CLASS,
      'data-right-tab': opts.id,
    })
  }
}

/**
 * 注册并控制一个右栏看板 tab。
 *
 * @param ctx - client half 的 apply(ctx) 上下文（需已注入 sidebarRight/sidebarRightTabs/slots）
 * @param opts - tab 类型与正文挂载
 * @returns 打开/关闭句柄；服务缺失时抛错，由调用方决定降级
 */
export function registerRightTab(ctx: unknown, opts: RightTabOptions): RightTabHandle {
  const c = (ctx ?? {}) as ClientCtxLike
  const tabs = c.sidebarRightTabs
  const sidebar = c.sidebarRight
  const slots = c.slots

  if (tabs === undefined || typeof tabs.register !== 'function') {
    throw new Error('sidebarRightTabs 服务不可用（DSH 官方右侧栏未加载）')
  }
  if (sidebar === undefined || typeof sidebar.openTab !== 'function') {
    throw new Error('sidebarRight 服务不可用（DSH 官方右侧栏未加载）')
  }

  injectHostStyles()

  const disposers: Array<() => void> = []
  const runEffect = (fn: () => unknown, label: string): void => {
    try {
      if (typeof c.effect === 'function') {
        c.effect(fn, label)
        return
      }
      const result = fn()
      if (typeof result === 'function') disposers.push(result as () => void)
    } catch (error) {
      console.error('[page-kit] 右栏注册失败 ' + label + ':', error)
    }
  }

  // ① 类型：静态声明（kind/title/keepMounted）
  runEffect(
    () => tabs.register!({
      id: opts.id,
      kind: opts.kind,
      title: () => opts.title,
      // 切到别的 tab/收起时保留正文，避免每次点开都重建 DOM 与重新取数
      keepMounted: true,
    }),
    'tab-type:' + opts.id,
  )

  // ② 正文：keyed slot，key = 类型 id
  if (slots !== undefined && typeof slots.register === 'function') {
    const body = makeBody(opts)
    try {
      if (typeof slots.inject === 'function') {
        slots.inject('sidebar.right.pane.tab', () => slots.register!({
          name: 'sidebar.right.pane.tab',
          key: opts.id,
        }, body))
      } else {
        slots.register({ name: 'sidebar.right.pane.tab', key: opts.id }, body)
      }
    } catch (error) {
      console.error('[page-kit] 右栏正文注册失败 ' + opts.id + ':', error)
    }
  } else {
    console.error('[page-kit] slots 服务不可用，右栏正文未注册 ' + opts.id)
  }

  const open = (): boolean => {
    try {
      sidebar.openTab!(opts.kind)
      return true
    } catch (error) {
      // 无会话在屏（hero 画面）或 kind 未注册：如实报错，不假装打开
      console.error('[page-kit] 右栏打开失败 ' + opts.kind + ':', error)
      return false
    }
  }

  const isActive = (): boolean => {
    try {
      if (typeof sidebar.isExpanded === 'function' && sidebar.isExpanded() === false) return false
      if (typeof sidebar.active !== 'function') return false
      const tab = sidebar.active()
      return tab !== undefined && tab !== null && tab.kind === opts.kind
    } catch {
      return false
    }
  }

  const close = (): void => {
    if (!isActive()) return
    try {
      const tab = sidebar.active?.()
      if (tab !== undefined && tab !== null && tab.id !== undefined) sidebar.close?.(tab.id)
    } catch (error) {
      console.error('[page-kit] 右栏关闭失败 ' + opts.kind + ':', error)
    }
  }

  const toggle = (): void => {
    if (isActive()) close()
    else open()
  }

  const dispose = (): void => {
    // 卸载前先关掉自己的 tab，避免留下一个没有正文的僵尸 tab
    close()
    for (const disposeReg of disposers.splice(0)) {
      try {
        disposeReg()
      } catch {
        // 幂等收尾
      }
    }
  }

  return { open, toggle, close, isActive, dispose }
}
