/**
 * 项目看板 board-mount —— 生命周期委托 page-kit board-shell；
 * 页面保留视图状态机（board / req-detail / task-detail / triage）、
 * fetch/render、事件委派、SSE 订阅与会话跳转。
 *
 * @module dsh-pmboard/client/board-mount
 */
import type { BoardState, TriageRecord } from './types.ts'
import {
  BOARD_VIEW_SELECTOR, PANEL_NAME, ACTIVE_ATTR, OTHER_ACTIVE_ATTRS,
} from './dom.ts'
import {
  buildBoard, buildEmpty, buildError, buildReqDetail, buildTaskDetail, buildTriage,
} from './view.ts'
import * as api from './api.ts'
import { jumpToSession, windowServiceAccess } from './session-jump.ts'
import { createBoardShell } from '@pi-investment/page-kit/client'

const POLL_MS = 20000

type ViewMode =
  | { kind: 'board' }
  | { kind: 'req'; reqId: string }
  | { kind: 'task'; taskId: string }
  | { kind: 'triage' }

export interface BoardController {
  openBoard(): void
  closeBoard(): void
  toggleBoard(): void
  getSnapshot(): { boardOpen: boolean }
  refresh(): void
}

export function createBoardController(): BoardController {
  const ctrl: BoardController = {
    openBoard: () => {}, closeBoard: () => {}, toggleBoard: () => {},
    getSnapshot: () => ({ boardOpen: false }),
    refresh: () => {},
  }
  return ctrl
}

export function mountBoard(controller: BoardController): () => void {
  let state: BoardState | undefined
  let triages: TriageRecord[] = []
  let mode: ViewMode = { kind: 'board' }
  let viewEl: HTMLElement | undefined
  let unsubEvents: (() => void) | undefined

  // ---- 渲染 ------------------------------------------------------------

  const render = (): void => {
    if (viewEl === undefined) return
    if (state === undefined) { viewEl.innerHTML = buildEmpty(); return }
    switch (mode.kind) {
      case 'board':
        viewEl.innerHTML = buildBoard(state)
        break
      case 'req': {
        const req = state.requirements.find(r => r.id === mode.reqId)
        viewEl.innerHTML = req ? buildReqDetail(req, state.tasks) : buildBoard(state)
        if (!req) mode = { kind: 'board' }
        break
      }
      case 'task': {
        const task = state.tasks.find(t => t.id === mode.taskId)
        const req = task ? state.requirements.find(r => r.id === task.requirementId) : undefined
        viewEl.innerHTML = task ? buildTaskDetail(task, req) : buildBoard(state)
        if (!task) mode = { kind: 'board' }
        break
      }
      case 'triage':
        viewEl.innerHTML = buildTriage(triages, state)
        break
    }
  }

  // ---- 数据 ------------------------------------------------------------

  const fetchAll = async (): Promise<void> => {
    try {
      const [s, t] = await Promise.all([api.fetchState(), api.fetchTriage()])
      state = s
      triages = t.pending
      render()
    } catch (err) {
      if (viewEl !== undefined) viewEl.innerHTML = buildError(String(err))
    }
  }

  // SSE：台账变更即刷新（revision 单调即接受）
  const startEvents = (): void => {
    unsubEvents?.()
    unsubEvents = api.subscribeEvents(() => { void fetchAll() })
  }

  // ---- 事件委派 --------------------------------------------------------

  const onClick = (ev: MouseEvent): void => {
    const target = ev.target as Element
    const el = target.closest<HTMLElement>('[data-action]')
    if (el === null || state === undefined) return
    const action = el.dataset.action ?? ''

    switch (action) {
      case 'refresh':
        void fetchAll()
        return
      case 'new-req': {
        const title = window.prompt('需求标题')
        if (title && title.trim()) {
          void api.createReq({ title: title.trim() }).then(() => fetchAll()).catch(e => window.alert(String(e)))
        }
        return
      }
      case 'open-req':
        if (el.dataset.req) { mode = { kind: 'req', reqId: el.dataset.req }; render() }
        return
      case 'open-task':
        if (el.dataset.task) { mode = { kind: 'task', taskId: el.dataset.task }; render() }
        return
      case 'back':
        mode = { kind: 'board' }; render()
        return
      case 'back-req':
        mode = { kind: 'req', reqId: el.dataset.req ?? '' }; render()
        return
      case 'move-req': {
        const reqId = state.requirements.find(r => mode.kind === 'req' && r.id === mode.reqId)?.id
        const to = el.dataset.to
        if (reqId && to) {
          void api.moveReq({ id: reqId, to, actor: 'human' }).then(() => fetchAll()).catch(e => window.alert(String(e)))
        }
        return
      }
      case 'add-comment': {
        const input = viewEl?.querySelector<HTMLInputElement>('[data-role="comment-input"]')
        const body = input?.value.trim()
        if (body && el.dataset.target && el.dataset.id) {
          void api.addComment({ target: el.dataset.target as 'req' | 'task', id: el.dataset.id, body, actor: 'human' })
            .then(() => fetchAll())
            .catch(e => window.alert(String(e)))
        }
        return
      }
      case 'jump-session': {
        const sid = el.dataset.sid
        if (sid) {
          void jumpToSession(windowServiceAccess(), sid).then(result => {
            if (result === 'archived') window.alert('该会话已归档（日志保留，侧栏不可见）')
            else if (result === 'missing') window.alert('该会话不在当前列表（可能已删除）')
            else if (result === 'unavailable') window.alert('会话服务暂不可用')
          })
        }
        return
      }
      case 'triage-confirm': {
        const triageId = el.dataset.triage
        if (!triageId) return
        // 按建议动作确认：有 targetId 走 bind_req，否则 create_req
        const tri = triages.find(t => t.id === triageId)
        if (tri?.suggestedAction === 'bind_req' && tri.suggestedTargetId) {
          void api.triageConfirm({ triageId, action: 'bind_req', targetId: tri.suggestedTargetId }).then(() => fetchAll()).catch(e => window.alert(String(e)))
        } else {
          void api.triageConfirm({ triageId, action: 'create_req' }).then(() => fetchAll()).catch(e => window.alert(String(e)))
        }
        return
      }
      case 'triage-rebind': {
        // 显示改绑宿主（select 已在 triage 视图内）
        const host = viewEl?.querySelector<HTMLElement>('.dsh-pm-rebind-host')
        if (host) {
          host.style.display = 'flex'
          host.dataset.triage = el.dataset.triage ?? ''
        }
        return
      }
      case 'triage-rebind-confirm': {
        const host = viewEl?.querySelector<HTMLElement>('.dsh-pm-rebind-host')
        const triageId = host?.dataset.triage
        const select = host?.querySelector<HTMLSelectElement>('[data-role="rebind-select"]')
        if (triageId && select?.value) {
          void api.triageRebind({ triageId, targetId: select.value }).then(() => fetchAll()).catch(e => window.alert(String(e)))
        }
        return
      }
      case 'triage-reject': {
        const triageId = el.dataset.triage
        if (triageId) {
          void api.triageReject({ triageId }).then(() => fetchAll()).catch(e => window.alert(String(e)))
        }
        return
      }
    }
  }

  // ---- board-shell 生命周期 --------------------------------------------

  const shell = createBoardShell({
    prefix: 'dsh-pm',
    panelName: PANEL_NAME,
    activeAttr: ACTIVE_ATTR,
    otherActiveAttrs: OTHER_ACTIVE_ATTRS,
    pollMs: POLL_MS,
    pauseOnHidden: true,
    buildContainer: () => {
      const el = document.createElement('div')
      el.dataset.dshPmView = ''
      el.className = 'dsh-pm-view'
      return el
    },
    onMount: (container) => {
      viewEl = container
      container.addEventListener('click', onClick)
      void fetchAll()
      startEvents()
      return () => {
        container.removeEventListener('click', onClick)
        unsubEvents?.()
        unsubEvents = undefined
        viewEl = undefined
      }
    },
    onPoll: () => { void fetchAll() },
    onOpen: () => { void fetchAll() },
  })

  const ctrl = controller as any
  ctrl.openBoard = shell.open
  ctrl.closeBoard = shell.close
  ctrl.toggleBoard = shell.toggle
  ctrl.getSnapshot = () => ({ boardOpen: shell.isActive() })
  ctrl.refresh = () => { void fetchAll() }

  return () => {
    shell.dispose()
  }
}
