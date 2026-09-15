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
  buildBoard, buildEmpty, buildError, buildReqDetail, buildTaskDetail, buildTasksPage, buildTriage,
  defaultListDirFor, LIST_PAGE_SIZE_DEFAULT, LIST_PAGE_SIZES,
  type BoardViewKind, type ListSortDir, type ListSortKey, type ListViewOpts,
} from './view.ts'
import * as api from './api.ts'
import { archivedSessionIds, jumpToSession, windowServiceAccess } from './session-jump.ts'
import { createBoardShell } from '@pi-investment/page-kit/client'

const POLL_MS = 20000

/** 看板视图偏好的持久键（前端本地，不入台账）。 */
const VIEW_PREF_KEY = 'dsh-pmboard:view'

/** 读取视图偏好：非法/不可用一律回落泳道。 */
function readViewPref(): BoardViewKind {
  try {
    const raw = sessionStorage.getItem(VIEW_PREF_KEY)
    return raw === 'list' ? 'list' : 'lanes'
  } catch { return 'lanes' }
}

/** 写入视图偏好（隐私模式等场景静默失败）。 */
function writeViewPref(view: BoardViewKind): void {
  try { sessionStorage.setItem(VIEW_PREF_KEY, view) } catch { /* 忽略 */ }
}

/** 列表视图偏好（排序键/方向/每页条数）的持久键。 */
const LIST_PREF_KEY = 'dsh-pmboard:list'

interface ListPref { sortKey: ListSortKey; sortDir: ListSortDir; pageSize: number }

const LIST_SORT_KEYS: readonly ListSortKey[] = ['stage', 'progress', 'updated', 'created', 'title']

/** 读取列表偏好：任何非法值一律回落默认（阶段升序 / 每页 10）。 */
function readListPref(): ListPref {
  const fallback: ListPref = { sortKey: 'stage', sortDir: 'asc', pageSize: LIST_PAGE_SIZE_DEFAULT }
  try {
    const raw = sessionStorage.getItem(LIST_PREF_KEY)
    if (raw === null) return fallback
    const parsed = JSON.parse(raw) as Partial<ListPref>
    const sortKey = typeof parsed.sortKey === 'string' && (LIST_SORT_KEYS as readonly string[]).includes(parsed.sortKey)
      ? parsed.sortKey as ListSortKey
      : fallback.sortKey
    const sortDir: ListSortDir = parsed.sortDir === 'asc' || parsed.sortDir === 'desc'
      ? parsed.sortDir
      : defaultListDirFor(sortKey)
    const pageSize = typeof parsed.pageSize === 'number' && LIST_PAGE_SIZES.includes(parsed.pageSize)
      ? parsed.pageSize
      : LIST_PAGE_SIZE_DEFAULT
    return { sortKey, sortDir, pageSize }
  } catch { return fallback }
}

type ViewMode =
  | { kind: 'board' }
  | { kind: 'req'; reqId: string }
  | { kind: 'task'; taskId: string }
  | { kind: 'tasks' }
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
  // 看板视图种类（泳道 / 列表）——纯前端偏好，不入台账；切换即重绘
  let boardView: BoardViewKind = readViewPref()
  // 列表视图的排序 / 分页状态（同样纯前端；page 不持久，回来不落在空页）
  const listPref = readListPref()
  let listSortKey: ListSortKey = listPref.sortKey
  let listSortDir: ListSortDir = listPref.sortDir
  let listPageSize: number = listPref.pageSize
  let listPage = 1
  let viewEl: HTMLElement | undefined
  let unsubEvents: (() => void) | undefined

  const listOpts = (): ListViewOpts => ({
    sortKey: listSortKey, sortDir: listSortDir, page: listPage, pageSize: listPageSize,
  })

  /** 已归档会话 id 集合（渲染时实时读取 → 归档/取消归档后下次重绘即生效）。 */
  const archivedSids = (): ReadonlySet<string> => archivedSessionIds()

  const writeListPref = (): void => {
    try {
      sessionStorage.setItem(LIST_PREF_KEY, JSON.stringify({
        sortKey: listSortKey, sortDir: listSortDir, pageSize: listPageSize,
      }))
    } catch { /* 忽略 */ }
  }

  // ---- 渲染 ------------------------------------------------------------

  const render = (): void => {
    if (viewEl === undefined) return
    if (state === undefined) { viewEl.innerHTML = buildEmpty(); return }
    switch (mode.kind) {
      case 'board':
        viewEl.innerHTML = buildBoard(state, Date.now(), boardView, listOpts(), archivedSids())
        break
      case 'req': {
        const req = state.requirements.find(r => r.id === mode.reqId)
        viewEl.innerHTML = req
          ? buildReqDetail(req, state.tasks, Date.now(), archivedSids())
          : buildBoard(state, Date.now(), boardView, listOpts(), archivedSids())
        if (!req) mode = { kind: 'board' }
        else void verifyDocExistence()
        break
      }
      case 'task': {
        const task = state.tasks.find(t => t.id === mode.taskId)
        const req = task ? state.requirements.find(r => r.id === task.requirementId) : undefined
        viewEl.innerHTML = task
          ? buildTaskDetail(task, req, Date.now(), state.tasks, archivedSids())
          : buildBoard(state, Date.now(), boardView, listOpts(), archivedSids())
        if (!task) mode = { kind: 'board' }
        break
      }
      case 'tasks':
        viewEl.innerHTML = buildTasksPage(state)
        break
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
    // 分页控件由 page-kit renderPagination 渲染（data-pmpage，无 data-action）
    const pageEl = target.closest<HTMLElement>('[data-pmpage]')
    if (pageEl !== null && state !== undefined) {
      const p = Number(pageEl.dataset.pmpage)
      if (Number.isFinite(p) && p >= 1) { listPage = p; render() }
      return
    }
    const el = target.closest<HTMLElement>('[data-action]')
    if (el === null || state === undefined) return
    const action = el.dataset.action ?? ''

    switch (action) {
      case 'refresh':
        void fetchAll()
        return
      case 'switch-view': {
        const next = el.dataset.view
        if (next === 'lanes' || next === 'list') {
          boardView = next
          writeViewPref(next)
          mode = { kind: 'board' }
          render()
        }
        return
      }
      case 'list-sort': {
        // 同键再点 = 切换升降序；换键 = 用该键的默认方向；排序变化回到第 1 页
        const key = el.dataset.key as ListSortKey | undefined
        if (key === undefined || !(LIST_SORT_KEYS.includes(key))) return
        if (key === listSortKey) {
          listSortDir = listSortDir === 'asc' ? 'desc' : 'asc'
        } else {
          listSortKey = key
          listSortDir = defaultListDirFor(key)
        }
        listPage = 1
        writeListPref()
        render()
        return
      }
      case 'open-doc': {
        const path = el.dataset.path
        if (path) void openDocModal(path)
        return
      }
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
      case 'open-tasks':
        mode = { kind: 'tasks' }
        render()
        return
      case 'new-task': {
        // 人工建卡（agent 走 reqboard_decompose 批量拆分）；建完留在详情页由 fetchAll 重绘
        const reqId = el.dataset.id
        if (!reqId) return
        const title = window.prompt('任务标题')
        if (title && title.trim()) {
          void api
            .createTask({ requirementId: reqId, title: title.trim(), phase: 'implement', side: 'fullstack' })
            .then(() => fetchAll())
            .catch(e => window.alert(String(e)))
        }
        return
      }
      case 'back':
        mode = { kind: 'board' }; render()
        return
      case 'back-req':
        mode = { kind: 'req', reqId: el.dataset.req ?? '' }; render()
        return
      case 'move-req': {
        // 卡面按钮自带 data-id（泳道图直接操作）；详情页闸门按钮退回用当前详情需求
        const reqId = el.dataset.id ?? (mode.kind === 'req' ? mode.reqId : undefined)
        const to = el.dataset.to
        if (reqId && to) {
          void api
            .moveReq({ id: reqId, to, actor: 'human', reason: el.dataset.id ? '看板泳道卡面操作' : '需求详情页操作' })
            .then(() => fetchAll())
            .catch(e => window.alert(String(e)))
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
      case 'verify-pass': {
        const reqId = el.dataset.id
        if (reqId) {
          void api.verifyPass({ id: reqId }).then(() => fetchAll()).catch(e => window.alert(String(e)))
        }
        return
      }
      case 'verify-rework': {
        const reqId = el.dataset.id
        if (!reqId) return
        const note = window.prompt('退回返工的意见（窗口会按它整改）')
        if (note === null) return
        void api
          .verifyRework({ id: reqId, note: note.trim() || '（未填意见）' })
          .then(() => fetchAll())
          .catch(e => window.alert(String(e)))
        return
      }
      case 'archive-req': {
        const reqId = el.dataset.id
        if (reqId) {
          void api.archiveReq({ id: reqId }).then(() => fetchAll()).catch(e => window.alert(String(e)))
        }
        return
      }
      case 'plan-approve': {
        const reqId = el.dataset.id
        if (reqId) {
          void api
            .approvePlan({ id: reqId })
            .then(() => fetchAll())
            .catch(e => window.alert(String(e)))
        }
        return
      }
      case 'plan-reject': {
        const reqId = el.dataset.id
        if (!reqId) return
        const reason = window.prompt('退回理由（窗口会按它重写计划）')
        if (reason === null) return
        void api
          .rejectPlan({ id: reqId, reason: reason.trim() || '（未填理由）' })
          .then(() => fetchAll())
          .catch(e => window.alert(String(e)))
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
          // 乙流程人工门：create_req 前读取可编辑卡上的 名称/分类（人工可改，空则不覆盖）
          const card = el.closest<HTMLElement>('.dsh-pm-triage')
          const title = card?.querySelector<HTMLInputElement>('[data-role="triage-title"]')?.value.trim()
          const category = card?.querySelector<HTMLSelectElement>('[data-role="triage-category"]')?.value
          void api.triageConfirm({
            triageId,
            action: 'create_req',
            ...(title ? { title } : {}),
            ...(category ? { category } : {}),
          }).then(() => fetchAll()).catch(e => window.alert(String(e)))
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

  /** 每页条数下拉（<select> 走 change，不走 click）。 */
  const onChange = (ev: Event): void => {
    const target = ev.target as Element | null
    if (target === null || typeof target.closest !== 'function') return

    // 列表每页条数选择器
    const listSizeEl = target.closest<HTMLSelectElement>('[data-action="list-size"]')
    if (listSizeEl !== null) {
      const size = Number(listSizeEl.value)
      if (!LIST_PAGE_SIZES.includes(size)) return
      listPageSize = size
      listPage = 1
      writeListPref()
      render()
      return
    }
  }

  /** 打开文档查看弹窗：fetch 文件内容，在 overlay 弹窗里展示（纯文本 pre-wrap）。 */
  const openDocModal = async (path: string): Promise<void> => {
    let content = ''
    let error = ''
    try {
      const res = await fetch('/dashboard/api/reqboard/file?path=' + encodeURIComponent(path))
      const data = await res.json() as { success?: boolean; data?: { content?: string }; error?: string }
      if (data.success === true && data.data?.content !== undefined) {
        content = data.data.content
      } else {
        error = data.error ?? '文件打开失败'
      }
    } catch (e) {
      error = '文件打开失败：' + String(e)
    }

    const overlay = document.createElement('div')
    overlay.className = 'dsh-pm-doc-modal-overlay'

    const modal = document.createElement('div')
    modal.className = 'dsh-pm-doc-modal'

    const head = document.createElement('div')
    head.className = 'dsh-pm-doc-modal-head'
    const title = document.createElement('span')
    title.className = 'dsh-pm-doc-modal-title'
    title.textContent = path
    const close = document.createElement('button')
    close.type = 'button'
    close.className = 'dsh-pm-btn'
    close.textContent = '关闭'
    head.append(title, close)

    const body = document.createElement('div')
    body.className = 'dsh-pm-doc-modal-body'
    if (error) {
      body.textContent = error
    } else {
      const pre = document.createElement('pre')
      pre.textContent = content
      body.append(pre)
    }

    modal.append(head, body)
    overlay.append(modal)

    const closeModal = (): void => { overlay.remove() }
    close.addEventListener('click', closeModal)
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal() })
    document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') closeModal() }, { once: true })

    document.body.appendChild(overlay)
  }

  /** 校验文档存在性：不存在的文档（未落盘/路径错误）标注缺失并禁止点击，不当作有效文档展示。 */
  const verifyDocExistence = async (): Promise<void> => {
    if (viewEl === undefined) return
    const items = viewEl.querySelectorAll<HTMLElement>('[data-doc-path]')
    await Promise.all(Array.from(items).map(async (li) => {
      const path = li.dataset.docPath
      if (!path) return
      let exists = false
      try {
        const res = await fetch('/dashboard/api/reqboard/file?path=' + encodeURIComponent(path))
        const data = await res.json() as { success?: boolean }
        exists = data.success === true
      } catch { exists = false }
      if (!exists) {
        li.classList.add('is-missing')
        li.setAttribute('title', '文件不存在（未落盘或路径错误）')
        const btn = li.querySelector<HTMLElement>('[data-action="open-doc"]')
        if (btn) {
          btn.removeAttribute('data-action')
          btn.classList.add('dsh-pm-doc-missing')
        }
      }
    }))
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
      container.addEventListener('change', onChange)
      void fetchAll()
      startEvents()
      return () => {
        container.removeEventListener('click', onClick)
        container.removeEventListener('change', onChange)
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
