/**
 * BoardPanelHost 契约单测（REQ-260928185112-e20d FR-2 / 任务卡 t-48d9a4）。
 *
 * 薄宿主不重写看板：本用例只验契约——渲染出与旧 buildContainer 同形的容器，
 * 且注入的 usePanelInfo 会被订阅（activePanelId 轮询门闩的数据来源）。
 * attachBoard 的生命周期（dispose 释放定时器/监听/SSE）由 tests/board-attach.test.ts 覆盖。
 *
 * 用 react-dom/server 的静态渲染：node 环境无 DOM，只验「渲染契约」与「宿主真的订阅了面板信息」。
 */
import { describe, it, expect } from 'vitest'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { BoardPanelHost, type PanelInfoLike } from '../src/client/page/host.ts'
import { PANEL_ID } from '../src/client/dom.ts'

/** 静态渲染一个组件（宿主返回 ReactNode；这里只关心 HTML 字符串）。 */
const render = (host: unknown): string => renderToStaticMarkup(createElement(host as never))

describe('BoardPanelHost（main 插槽薄宿主，createElement 无 JSX）', () => {
  it('渲染与旧 buildContainer 同形的容器（class=dsh-pm-view + data-dsh-pm-view）', () => {
    const html = render(BoardPanelHost)
    expect(html).toContain('class="dsh-pm-view"')
    expect(html).toContain('data-dsh-pm-view=""')
  })

  it('订阅注入的 usePanelInfo（activePanelId 门闩的数据来源）', () => {
    const infos: PanelInfoLike[] = []
    const usePanelInfo = <S,>(selector: (info: PanelInfoLike) => S): S => {
      const info: PanelInfoLike = { activePanelId: PANEL_ID }
      infos.push(info)
      return selector(info)
    }

    const Wrapper = (): unknown => BoardPanelHost({ usePanelInfo })
    const html = render(Wrapper)

    expect(infos).toEqual([{ activePanelId: PANEL_ID }])
    expect(html).toContain('dsh-pm-view')
  })

  it('缺 usePanelInfo 时用恒可见兜底（不抛、不误停轮询）', () => {
    const html = render(BoardPanelHost)
    expect(html).toContain('dsh-pm-view')
  })
})
