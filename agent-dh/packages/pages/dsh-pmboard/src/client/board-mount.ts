/**
 * 项目看板 board-mount —— 生命周期委托 ./board-shell；
 * 页面保留视图状态机（board / req-detail / task-detail / triage）、
 * fetch/render、事件委派、SSE 订阅与会话跳转。
 *
 * @module dsh-pmboard/client/board-mount
 */
import type { BoardState, RequirementRecord, TriageRecord } from './types.ts'
import {
  PANEL_NAME,
  ACTIVE_ATTR,
  OTHER_ACTIVE_ATTRS,
} from './dom.ts'
import {
  buildBoard, buildEmpty, buildError, buildReqDetail, buildTaskDetail, buildTasksPage, buildTriage,
  defaultListDirFor, LIST_PAGE_SIZE_DEFAULT, LIST_PAGE_SIZES,
  type BoardViewKind, type ListSortDir, type ListSortKey, type ListViewOpts,
} from './view.ts'
import * as api from './api.ts'
import { openDocInSidebar, resolveCurrentSessionId } from './open-doc.ts'
import { archivedSessionIds, jumpToSession, windowServiceAccess, type SessionJumpResult } from './session-jump.ts'
import { createBoardShell } from './board-shell.js'
import { fmt } from '../domain/text/fmt.js'
import { renderStageNode } from './stage-panel.ts'
import { hasInjectionWindow, renderInjectionInfo } from './injection-info.ts'
import { renderTokenPlaceholder, renderTokenTab } from './token-info.ts'
import { renderMarksBlock, renderMarksPlaceholder } from './marks-info.ts'
import type { StageOverview, StageKey } from '../shared/protocol.ts'

const POLL_MS = 20000

/** 「验收通过」确认文案与覆盖说明（REQ-a8d582 FR-1/FR-4）。 */
export interface VerifyConfirmCopy {
  /** 弹给人看的确认文案（含"不通过 / 未裁决"计数）。 */
  message: string
  /**
   * 需要显式覆盖时才给（有不合格项或尚无验收材料）。
   * 全过且材料齐全时为 undefined —— 那种通过**不是覆盖**，不该在台账留覆盖痕迹。
   */
  overrideDetail?: string
}

/**
 * 装配「验收通过」的确认文案与覆盖说明（REQ-a8d582 FR-1/FR-4）。
 *
 * 为什么区分两种通过：覆盖是一种**例外**，只有"人已知有不合格项 / 尚无验收材料还坚持通过"
 * 才成立；全过且材料齐全时的通过不该带覆盖记录（否则台账里全是噪声，复盘时读不出例外）。
 * 覆盖说明由计数与不合格项摘要自动装配——不让人手填：那是"是/否"确认框，不是写作文。
 */
export function verifyConfirmCopy(req: RequirementRecord | undefined): VerifyConfirmCopy {
  const v = req?.verification
  if (v === undefined) {
    return {
      message: '该需求尚无验收材料（本次通过没有验收证据）。\n确认后按「覆盖通过」直接归档，是否继续？',
      overrideDetail: '看板覆盖通过：尚无验收材料（无验收证据）',
    }
  }
  const items = v.sheet?.items ?? []
  const passed = items.filter(i => i.status === 'passed').length
  const failedItems = items.filter(i => i.status === 'failed')
  const pending = items.filter(i => i.status === 'pending').length
  const version = v.sheet?.version ?? 0
  if (failedItems.length === 0 && pending === 0) {
    return { message: '验收单 v' + version + '：' + passed + ' 项全部通过。\n验收通过即归档，是否继续？' }
  }
  const samples = failedItems.slice(0, 3).map(i => '✗ ' + i.criterion.slice(0, 60))
  return {
    message: '验收单 v' + version + '：通过 ' + passed + ' / 不通过 ' + failedItems.length + ' / 未裁决 ' + pending + '。\n'
      + (samples.length > 0 ? samples.join('\n') + '\n' : '')
      + '确认后按「覆盖通过」归档（会留下覆盖记录），是否继续？',
    overrideDetail: '看板覆盖通过：验收单 v' + version + '，不通过 ' + failedItems.length + ' 项 / 未裁决 ' + pending + ' 项',
  }
}

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

/**
 * 会话跳转结果的**明确反馈**（REQ-31e11f #5：不允许点了没反应）。
 * 'opened' 不打扰（已经跳过去了）；其余结果必须能说清“为什么没跳”。
 * 导出以便单测覆盖（纯函数，无 DOM 依赖）。
 */
export function jumpResultMessage(result: SessionJumpResult, sid: string): string {
  const short = sid.length > 18 ? sid.slice(0, 18) + '…' : sid
  switch (result) {
    case 'archived':
      return '该会话已归档（' + short + '）：日志保留、侧栏不可见，无法跳转'
    case 'missing':
      return '该会话不在当前会话列表（' + short + '）：可能已删除或不在当前工作区'
    case 'unavailable':
      return '会话服务暂不可用（页面注入未就绪），请刷新页面后重试'
    case 'opened':
      return ''
    default:
      return '会话跳转结果未知：' + String(result)
  }
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
  // 需求详情里当前选中的阶段节点（分段控件选中态；跨 SSE 重绘保留）
  let activeStage: string | undefined
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

  /**
   * 阶段导航（分段控件）选中态：data-active="true" 切到当前 stage，清掉同组其它按钮。
   * 没有它，分段控件看不出「现在在看哪个节点」（A 的样式已就绪，缺的是这里的状态切换）。
   */
  const setStageNavActive = (stage: string | undefined): void => {
    if (viewEl === undefined) return
    viewEl.querySelectorAll<HTMLElement>('[data-action="load-stage"]').forEach(btn => {
      if (stage !== undefined && btn.dataset.stage === stage) btn.setAttribute('data-active', 'true')
      else btn.removeAttribute('data-active')
    })
  }

  // ---- 渲染 ------------------------------------------------------------

  const render = (): void => {
    if (viewEl === undefined) return
    if (state === undefined) { viewEl.innerHTML = buildEmpty(); return }
    // mode 在闭包内可被事件回调改写，直接 switch 无法做判别收窄；取 const 快照后再收窄（类型层修复，无行为变化）
    const cur = mode
    switch (cur.kind) {
      case 'board':
        viewEl.innerHTML = buildBoard(state, Date.now(), boardView, listOpts(), archivedSids())
        break
      case 'req': {
        const req = state.requirements.find(r => r.id === cur.reqId)
        viewEl.innerHTML = req
          ? buildReqDetail(req, state.tasks, Date.now(), archivedSids())
          : buildBoard(state, Date.now(), boardView, listOpts(), archivedSids())
        if (!req) mode = { kind: 'board' }
        else {
          setStageNavActive(activeStage)
          void verifyDocExistence()
          // REQ-6f39b5：节点导航已删除，概览 Tab「当前阶段详情」进入即自动加载当前阶段
          void loadStageDetail(req.id, req.status)
          // REQ-422af1 t11：「本次注入了什么」只读块（按来源窗口回查留痕）
          void loadInjectionInfo(req.sourceSessionId)
          // REQ-a33899 t6：Token tab 内容（打开详情即预取，切到该 tab 直接可见）
          void loadTokenTab(req.id)
          // REQ-d3e61a T-5：条款接收状态（打开详情即取，红名单第一时间可见）
          void loadMarksBlock(req.id)
        }
        break
      }
      case 'task': {
        const task = state.tasks.find(t => t.id === cur.taskId)
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
    // 分页控件由 render/pagination 渲染（data-pmpage，无 data-action）
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
        // REQ-ff20ca t6：看板文档点击同样走官方右侧栏（弹窗已整套删除，无降级）
        const path = el.dataset.path
        if (path) openDocInSidebar(window.__dshPmCtx, path, resolveCurrentSessionId())
        return
      }
      // REQ-6f39b5 t-006：Tab 切换
      case 'switch-tab': {
        const tab = target.closest<HTMLElement>('.dsh-pm-tab')
        if (!tab) return
        const tabName = tab.dataset.tab
        if (!tabName) return
        
        // 切换 Tab active 状态
        const tabsContainer = tab.closest('.dsh-pm-detail')
        if (!tabsContainer) return
        
        tabsContainer.querySelectorAll('.dsh-pm-tab').forEach(t => {
          t.classList.remove('active')
        })
        tab.classList.add('active')
        
        // 切换内容区显示
        tabsContainer.querySelectorAll('.dsh-pm-tab-content').forEach(content => {
          content.classList.remove('active')
        })
        
        const targetContent = tabsContainer.querySelector(
          `.dsh-pm-tab-content[data-tab-content="${tabName}"]`
        )
        if (targetContent) {
          targetContent.classList.add('active')
        }
        // REQ-a33899 t6：Token tab 首次切到时确保已取数（打开详情时通常已预取）
        if (tabName === 'token') {
          const reqId = (tabsContainer as HTMLElement).dataset.detailReq
          if (reqId !== undefined && reqId.length > 0) void loadTokenTab(reqId)
        }
        return
      }
      // REQ-a33899 t6：Token 表点节点行 → 展开/收起该阶段任务明细
      case 'toggle-token-node': {
        const row = el.closest<HTMLElement>('.dsh-pm-tok-node')
        const stage = row?.dataset.stage
        if (row === null || stage === undefined) return
        const table = row.closest('table')
        table?.querySelectorAll<HTMLElement>('.dsh-pm-tok-sub').forEach((sub) => {
          if (sub.dataset.parentStage !== stage) return
          sub.style.display = sub.style.display === 'none' ? '' : 'none'
        })
        return
      }
      case 'load-stage': {
        const reqId = el.dataset.req
        const stage = el.dataset.stage
        if (reqId && stage) {
          activeStage = stage
          setStageNavActive(stage)
          void loadStageDetail(reqId, stage)
        }
        return
      }
      case 'auto-run-pause':
      case 'auto-run-resume':
      case 'auto-run-stop': {
        // 自动链控制面（REQ-4842fe t-3be71b）：暂停 / 继续 / 终止。
        // 继续 = 置 autoRun=true 并由服务端**立即触发一次推进事件**（推进器未装配时服务端如实说明）。
        const reqId = el.dataset.id ?? (mode.kind === 'req' ? mode.reqId : undefined)
        if (!reqId) return
        const act = el.dataset.action
        if (act === 'auto-run-stop' && !window.confirm('终止 = 暂停自动链；在跑/待跑的卡需人工取消（取消是人工闸门）。确定？')) return
        const on = act === 'auto-run-resume'
        const verb = act === 'auto-run-pause' ? '暂停' : on ? '继续' : '终止'
        void api.setAutoRun(reqId, on, fmt('看板控制面：{verb}', { verb }))
          .then(() => fetchAll())
          .catch(e => window.alert(String(e)))
        return
      }
      case 'toggle-subtasks':
        // 子卡区用原生 <details> 自己开合；这里只吃掉这次点击，避免冒泡到卡片的 open-task
        return
      case 'confirm-artifact': {
        const reqId = el.dataset.id
        const kind = el.dataset.kind
        if (reqId && kind) {
          void api.confirmArtifact({ id: reqId, kind })
            .then(() => fetchAll())
            .catch(e => window.alert(String(e)))
        }
        return
      }
      case 'submit-verdicts': {
        // 验收单逐项裁决（REQ-2e9473 t14）：从 DOM 收集每项 通过/不通过 + 意见
        const reqId = el.dataset.req
        const version = Number(el.dataset.version)
        const sheetEl = el.closest<HTMLElement>('.dsh-pm-vsheet')
        if (!reqId || !Number.isFinite(version) || sheetEl === null) return
        const verdicts: { itemId: string; status: 'passed' | 'failed'; opinion?: string }[] = []
        sheetEl.querySelectorAll<HTMLElement>('.dsh-pm-vitem').forEach((itemEl) => {
          const itemId = itemEl.dataset.itemId
          if (itemId === undefined) return
          const checked = itemEl.querySelector<HTMLInputElement>('input[type="radio"]:checked')
          if (checked === null) return
          const opinionEl = itemEl.querySelector<HTMLInputElement>('.dsh-pm-vitem-opinion')
          const opinion = opinionEl?.value.trim() ?? ''
          verdicts.push({
            itemId,
            status: checked.value === 'passed' ? 'passed' : 'failed',
            ...(opinion.length > 0 ? { opinion } : {}),
          })
        })
        if (verdicts.length === 0) { window.alert('请先逐项选择 通过/不通过'); return }
        void api.submitVerdicts({ id: reqId, version, verdicts })
          .then(() => fetchAll())
          .catch(e => window.alert(String(e)))
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
        if (el.dataset.req) { activeStage = undefined; mode = { kind: 'req', reqId: el.dataset.req }; render() }
        return
      case 'open-task':
        if (el.dataset.task) { mode = { kind: 'task', taskId: el.dataset.task }; render() }
        return
      case 'open-tasks':
        activeStage = undefined
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
        activeStage = undefined
        mode = { kind: 'board' }; render()
        return
      case 'back-req':
        activeStage = undefined
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
        if (!sid) return
        // 渲染时已知归档（chip 带 data-archived）→ 不发起跳转，直接给原因。
        // 旧实现把归档 chip 渲染成无 data-action 的灰 span，点击静默无反应（#5 真因）。
        if (el.dataset.archived === 'true') {
          window.alert(jumpResultMessage('archived', sid))
          return
        }
        void jumpToSession(windowServiceAccess(), sid)
          .then(result => {
            const msg = jumpResultMessage(result, sid)
            if (msg !== '') window.alert(msg)
          })
          .catch(e => window.alert('会话跳转失败：' + String(e)))
        return
      }
      case 'verify-pass': {
        const reqId = el.dataset.id
        if (!reqId) return
        // REQ-a8d582 FR-1：先把「不通过 / 未裁决」摆到人眼前再问是否仍要通过。
        // 取消 → 直接 return：一个请求都不发（验收标准 2 的"零副作用"就落在这里）。
        const target = state?.requirements.find(r => r.id === reqId)
        const copy = verifyConfirmCopy(target)
        if (!window.confirm(copy.message)) return
        void api
          .verifyPass({
            id: reqId,
            ...(copy.overrideDetail !== undefined ? { confirm_override: copy.overrideDetail } : {}),
          })
          .then(() => fetchAll())
          .catch(e => window.alert(String(e)))
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
        const reason = window.prompt('退回理由（窗口会按它重写拆分计划）')
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

  // （REQ-ff20ca t6）旧文档弹窗已整套删除；文档打开统一走 openDocInSidebar（官方右侧栏）。

  /**
   * 校验文档可打开性（REQ-b63a7d t4）：逐条 /file 预检 → **一次批量解析**。
   *
   * 为什么必须换：旧实现每个文档发一条 GET，路径只要不在 docs/ 内就被白名单判 403，
   * 控制台持续刷红（实测 142 条：源码类产物、仓库根相对、跨仓、伪路径全中）。批量端点
   * 由 host 单点判定（归一层 + fs）且恒 200 → 不再产生任何失败请求；判定原因直接展示，
   * 跨仓/伪路径不再被含糊地叫「文件不存在」。
   */
  const verifyDocExistence = async (): Promise<void> => {
    if (viewEl === undefined) return
    const items = Array.from(viewEl.querySelectorAll<HTMLElement>('[data-doc-path]'))
    if (items.length === 0) return
    const paths = Array.from(new Set(items.map(li => li.dataset.docPath ?? '').filter(p => p.length > 0)))
    if (paths.length === 0) return
    let verdicts: api.DocPathVerdictView[]
    try {
      verdicts = (await api.resolveReqDocs(paths)).results ?? []
    } catch {
      // 通道不可用 → 不做任何标记（宁可保持可点击，也不误标「缺失」；R-013 诚实降级）
      return
    }
    const byPath = new Map(verdicts.map(v => [v.path, v]))
    for (const li of items) {
      const path = li.dataset.docPath ?? ''
      const v = byPath.get(path)
      if (v === undefined || v.openable) continue
      li.classList.add('is-missing')
      li.setAttribute('title', v.reason ?? '文件不可打开')
      // 判为不可打开后移除预检锚点：DOM 上不再残留 data-doc-path
      li.removeAttribute('data-doc-path')
      const btn = li.querySelector<HTMLElement>('[data-action="open-doc"]')
      if (btn) {
        btn.removeAttribute('data-action')
        btn.classList.add('dsh-pm-doc-missing')
      }
    }
  }

  /** 加载单节点工作记录并渲染（REQ-31e11f v4：点哪个节点只看哪个）。 */
  const loadStageDetail = async (reqId: string, stage: string): Promise<void> => {
    const container = document.getElementById('dsh-pm-stage-detail-container')
    if (container === null) return
    container.innerHTML = '<div class="dsh-pm-empty">详情加载中…</div>'
    try {
      const res = await fetch('/dashboard/api/reqboard/requirements/' + encodeURIComponent(reqId) + '/stages', {
        signal: AbortSignal.timeout(8000),
      })
      if (!res.ok) {
        container.innerHTML = '<div class="dsh-pm-empty">详情暂不可用（HTTP ' + res.status + '）</div>'
        return
      }
      const json = await res.json() as { success?: boolean; data?: StageOverview }
      if (json.success === true && json.data !== undefined) {
        container.innerHTML = renderStageNode(json.data, stage as StageKey)
      } else {
        container.innerHTML = '<div class="dsh-pm-empty">详情暂不可用</div>'
      }
    } catch (e) {
      container.innerHTML = '<div class="dsh-pm-empty">详情加载失败：' + String(e) + '</div>'
    }
  }

  /**
   * 加载「本次注入」只读信息块（REQ-422af1 t11）。
   * 留痕不可用（端口未装配 / 接口失败）时不报错、不留白：渲染明确的空态「尚无记录」。
   */
  const loadInjectionInfo = async (sourceSessionId: string | undefined): Promise<void> => {
    const container = document.getElementById('dsh-pm-injection-info-container')
    if (container === null) return
    // 无来源窗口（人工建卡）→ 没有"本次注入"可言：保持空态，不拿全量留痕冒充本需求的注入。
    if (!hasInjectionWindow(sourceSessionId)) {
      container.innerHTML = renderInjectionInfo([])
      return
    }
    try {
      const info = await api.fetchInjectionInfo(sourceSessionId)
      container.innerHTML = renderInjectionInfo(info.available ? info.entries : [])
    } catch {
      container.innerHTML = renderInjectionInfo([])
    }
  }

  /**
   * 加载「🪙 Token」tab 内容（REQ-a33899 t6）：按当前需求 id 取 /requirements/:id/token。
   * 幂等（同一需求只取一次）；失败渲染明确空态，不报错不留白。
   */
  let tokenLoadedFor: string | undefined
  const loadTokenTab = async (reqId: string): Promise<void> => {
    const container = document.getElementById('dsh-pm-token-container')
    if (container === null) return
    if (tokenLoadedFor === reqId) return
    try {
      container.innerHTML = renderTokenTab(await api.fetchRequirementToken(reqId))
      tokenLoadedFor = reqId
    } catch {
      container.innerHTML = renderTokenPlaceholder('Token 数据暂不可用（接口失败或需求不存在）')
    }
  }

  /**
   * 加载「🏷 条款接收状态」（REQ-d3e61a T-5）：按当前需求 id 取 /requirements/:id/marks。
   * 不做"按 id 记住已加载"的缓存——详情页每次渲染都会重建容器，那种缓存会让同一需求
   * 重开时永远停在"加载中…"；这里只挡同一需求的并发重复请求。
   */
  let marksInFlight: string | undefined
  const loadMarksBlock = async (reqId: string): Promise<void> => {
    const container = document.getElementById('dsh-pm-marks-container')
    if (container === null) return
    if (marksInFlight === reqId) return
    marksInFlight = reqId
    try {
      container.innerHTML = renderMarksBlock(await api.fetchRequirementMarks(reqId))
    } catch {
      container.innerHTML = renderMarksPlaceholder('接收状态暂不可用（接口失败或需求不存在）')
    } finally {
      marksInFlight = undefined
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