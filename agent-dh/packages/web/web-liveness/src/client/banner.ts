/**
 * web-liveness 顶部横幅：三种状态一条 DOM。
 * 直接 DOM 注入（与 page-kit 的 toast / sidebar-entry 同款路子）—— 不依赖壳的 slot，
 * 框架换版也不会因为 slot 名对不上而静默失效。
 *
 * @module web-liveness/client/banner
 */
import type { LivenessPhase } from './watch.js'

export interface BannerRenderOptions {
  /** stale 态下"正在等用户停手再自动刷新"。 */
  pending?: boolean
}

export interface Banner {
  /** 按状态刷新横幅；`ok` 会把它收起来。 */
  render(phase: LivenessPhase, options?: BannerRenderOptions): void
  /** 撤下横幅并解绑。 */
  dispose(): void
}

const TEXT = {
  offline: '服务重启中，正在自动重连…… 此期间发送的消息可能发不出去，请稍候',
  stalePending: '服务已重启（代码可能已更新），你停手后页面会自动刷新',
  staleManual: '服务已重启，页面需要刷新才能用上新版本（反复出现请按 Cmd+Shift+R 硬刷新）',
} as const

/**
 * 创建横幅（纯 DOM，无 React）。
 * @param onReload - 点"立即刷新"时调用。
 */
export function createBanner(onReload: () => void): Banner {
  const bar = document.createElement('div')
  bar.className = 'dsh-wlv-bar'
  bar.dataset.phase = 'ok'
  bar.setAttribute('role', 'status')

  const text = document.createElement('span')
  text.className = 'dsh-wlv-text'

  const button = document.createElement('button')
  button.className = 'dsh-wlv-action'
  button.type = 'button'
  button.textContent = '立即刷新'
  button.addEventListener('click', onReload)

  bar.appendChild(text)
  bar.appendChild(button)
  document.body.appendChild(bar)

  return {
    render(phase, options) {
      if (phase === 'ok') {
        bar.dataset.phase = 'ok'
        return
      }
      text.textContent =
        phase === 'offline' ? TEXT.offline : options?.pending === true ? TEXT.stalePending : TEXT.staleManual
      bar.dataset.phase = phase
    },
    dispose() {
      button.removeEventListener('click', onReload)
      bar.remove()
    },
  }
}
