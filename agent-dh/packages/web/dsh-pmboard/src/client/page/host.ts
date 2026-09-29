/**
 * 看板页面宿主（main 插槽占用者）—— 薄 React 组件：只提供容器与生命周期，
 * 视图本身仍是命令式看板（board-mount.attachBoard）。
 *
 * 为什么不重写成 React：REQ-260928185112-e20d 明确「不重写命令式看板」。宿主只负责
 * 「挂载时 attach、卸载时 dispose」；keyed 插槽切 key 会卸载占用者，SSE/轮询/DOM 监听
 * 随之一并释放，不会在页面切换后留下常驻监听。
 *
 * 轮询门闩：keyed 插槽正常路径下「挂载 ≈ 在看」，这里仍订阅 usePanelInfo().activePanelId
 * 做防御性一致——!== PANEL_ID 时跳过本轮刷新（见 AttachBoardOptions.isActive）。
 *
 * @module dsh-pmboard/client/page/host
 */
import { createElement, useEffect, useRef, type ReactNode } from 'react'
import { attachBoard } from '../board-mount.ts'
import { PANEL_ID } from '../dom.ts'

/** 槽位运行时注入的面板信息（GlobalStandardProps.usePanelInfo 的选择器投影）。 */
export interface PanelInfoLike {
  /** 当前选中的全局主面板 id；null = 显示当前对话。 */
  readonly activePanelId: string | null
}

/** usePanelInfo 选择器 hook 的最小契约（由 main 插槽运行时注入）。 */
export type UsePanelInfo = <S>(selector: (info: PanelInfoLike) => S) => S

/** main 插槽占用者收到的 props（本宿主只消费 usePanelInfo）。 */
export interface BoardPanelHostProps {
  usePanelInfo?: UsePanelInfo
}

/**
 * 槽位运行时未注入 usePanelInfo 时的兜底：恒判「本面板在看」。
 *
 * 刻意**不是** hook 实现（不调用 useState/useEffect）：它只是同一位置上的固定兜底，
 * 调用点数量恒定，不会破坏 hooks 顺序；漏判「不在看」只会多轮询，漏判「在看」会停更。
 */
const ALWAYS_SELECT: PanelInfoLike = { activePanelId: PANEL_ID }

const ALWAYS_ACTIVE: UsePanelInfo = <S,>(selector: (info: PanelInfoLike) => S): S => selector(ALWAYS_SELECT)

/**
 * 面板宿主：容器一挂上就 attachBoard，卸载即 disposer。
 * 用 createElement（不用 JSX）——与 conversation-progress 同款写法。
 */
export function BoardPanelHost(props: BoardPanelHostProps = {}): ReactNode {
  const usePanelInfo: UsePanelInfo = typeof props.usePanelInfo === 'function' ? props.usePanelInfo : ALWAYS_ACTIVE
  const activePanelId = usePanelInfo((info) => info.activePanelId)
  const hostRef = useRef<HTMLElement | null>(null)
  // 可见性门闩走 ref：轮询 tick 每次读最新值，不必因面板切换重挂容器
  const activeRef = useRef<boolean>(activePanelId === PANEL_ID)
  activeRef.current = activePanelId === PANEL_ID

  useEffect(() => {
    const el = hostRef.current
    if (el === null) return
    return attachBoard(el, { isActive: () => activeRef.current })
  }, [])

  return createElement('div', {
    ref: hostRef,
    className: 'dsh-pm-view',
    'data-dsh-pm-view': '',
  })
}

export default BoardPanelHost
