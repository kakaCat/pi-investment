// @pi-investment/solve-kit · client 半：「我来解决」窗口选择器 + 投递（只投递，不建帖）。
// 从 dashboard-execution client/board-mount.ts 的 solve 实现抽象（2026-09-08, w-752decf5）：
// - createSolveKit(deps)：toast / 窗口选择器弹层 / POST 投递；页面负责事件委托与快照/会话源。
// - injectSolveStyles(prefix)：内置 toast/solvepop 样式（类名前缀隔离页面，如 dsh-exec / dsh-hld）。
// 页面接线：按钮 <button class="<pf>-solve" data-solve-task="任务名">我来解决</button> →
// 容器 click 委托 → kit.openPicker(btn, 'task', { name })；快照 resolveSnapshot 返回 null（数据已刷新）→ toast 提示重试。

export interface SolveCandidate {
  sid: string
  label: string
  current: boolean
}

export interface SolveSnapshot {
  kind: 'task' | 'error'
  snap: Record<string, unknown>
}

export interface SolveIdentity {
  name?: string
  index?: number
}

export interface SolveKitDeps {
  /** POST 端点（宿主页面独占 solve 路由，如 /dashboard/api/board/solve） */
  endpoint: string
  /** CSS 类前缀（页面隔离），如 'dsh-exec'（执行看板）/ 'dsh-hld'（持仓看板） */
  prefix: string
  /** 会话候选（页面注入 sessions/workspaces 后读取；[] = 无候选，直投主窗口） */
  candidates(): SolveCandidate[]
  /** 当前会话 id（from_session 语义；空串则由 host 回退主 root） */
  current(): string
  /** identity → 当前数据里的最新快照；列表已刷新找不到 → null（提示重试） */
  resolveSnapshot(kind: 'task' | 'error', identity: SolveIdentity): SolveSnapshot | null
  /** 浮层挂载宿主（默认 document.body）；点击按钮时容器通常已存在 */
  host?: HTMLElement | (() => HTMLElement | undefined)
}

export interface SolveKit {
  /** 飘字提示（ok=true 绿 / false 红） */
  toast(text: string, ok: boolean): void
  /** 点「我来解决」：弹窗口选择器（当前窗口置首带 ● 标）；无候选/无会话时直投 */
  openPicker(anchor: HTMLElement, kind: 'task' | 'error', identity: SolveIdentity): void
  /** 关闭弹层（页面 dispose 时调用） */
  close(): void
}

function cssFor(pf: string): string {
  return [
    '.' + pf + '-solve { flex:none; border:1px solid #c6e2ff; background:#ecf5ff; color:#409eff; border-radius:5px; padding:2px 9px; font-size:11.5px; line-height:1.7; cursor:pointer; white-space:nowrap; vertical-align:middle; }',
    '.' + pf + '-solve:hover { background:#d9ecff; border-color:#79bbff; }',
    '.' + pf + '-solve:active { background:#c6e2ff; }',
    '.' + pf + '-solvepop { position:fixed; z-index:9999; min-width:232px; max-width:300px; background:var(--panel,#fff); border:1px solid var(--border,#e4e7ed); border-radius:8px; box-shadow:0 6px 22px rgba(0,0,0,.16); padding:6px; font-size:12.5px; color:var(--body,#606266); }',
    '.' + pf + '-solvepop-head { padding:4px 8px 7px; color:var(--text,#303133); font-weight:600; font-size:12px; border-bottom:1px solid var(--line,#ebeef5); margin-bottom:4px; }',
    '.' + pf + '-solvepop-list { display:flex; flex-direction:column; max-height:264px; overflow-y:auto; }',
    '.' + pf + '-solvepop-item { border:none; background:transparent; text-align:left; padding:5px 8px; border-radius:5px; cursor:pointer; color:var(--body,#606266); font:inherit; font-size:12.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }',
    '.' + pf + '-solvepop-item:hover { background:var(--hover,rgba(128,128,128,.12)); }',
    '.' + pf + '-solvepop-item.cur { color:#409eff; font-weight:600; }',
    '.' + pf + '-solvepop-cancel { width:100%; margin-top:4px; border:none; background:transparent; color:var(--dim,#909399); font:inherit; font-size:12px; padding:4px; cursor:pointer; border-top:1px solid var(--line,#ebeef5); }',
    '.' + pf + '-solvepop-cancel:hover { color:var(--text,#303133); }',
    '.' + pf + '-toast { position:fixed; left:50%; bottom:54px; transform:translateX(-50%); z-index:10000; max-width:70vw; background:#303133; color:#fff; border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6; box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s; }',
    '.' + pf + '-toast.ok { background:#529b2e; }',
    '.' + pf + '-toast.err { background:#e64545; }',
    '.' + pf + '-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }',
  ].join('\n')
}

/** 注入 solve 样式一次（按前缀独立 style 标签）；返回清理函数。 */
export function injectSolveStyles(prefix: string): () => void {
  const id = 'dsh-solve-styles-' + prefix
  const existing = document.getElementById(id)
  if (existing !== null && existing.tagName === 'STYLE') return () => existing.remove()
  const style = document.createElement('style')
  style.id = id
  style.textContent = cssFor(prefix)
  ;(document.head ?? document.documentElement).appendChild(style)
  return () => { document.getElementById(id)?.remove() }
}

export function createSolveKit(deps: SolveKitDeps): SolveKit {
  const pf = deps.prefix
  let solvePop: HTMLDivElement | undefined
  let solveDocClean: (() => void) | undefined

  const close = (): void => {
    solveDocClean?.()
    solveDocClean = undefined
    if (solvePop !== undefined) { solvePop.remove(); solvePop = undefined }
  }

  const toast = (text: string, ok: boolean): void => {
    const el = document.createElement('div')
    el.className = pf + '-toast ' + (ok ? 'ok' : 'err')
    el.textContent = text
    document.body.appendChild(el)
    window.setTimeout(() => { el.classList.add('out'); window.setTimeout(() => el.remove(), 350) }, 4200)
  }

  /** POST endpoint（host 路由：自包含消息 → 目标 agent.followup） */
  const postSolve = async (kind: 'task' | 'error', snap: Record<string, unknown>, toSession?: string): Promise<void> => {
    const from = deps.current()
    try {
      const res = await fetch(deps.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, task: kind === 'task' ? snap : undefined, err: kind === 'error' ? snap : undefined, from_session: from || undefined, to_session: toSession }),
      })
      const j = await res.json().catch(() => null)
      if (j === null || j.success !== true) { toast('投递失败：' + String(j?.error ?? 'HTTP ' + res.status), false); return }
      const d = j.data as { delivered?: boolean; note?: string; error?: string } | undefined
      toast(d?.delivered === true ? '✓ ' + String(d?.note ?? '已投递') : '⚠ ' + String(d?.error ?? j.error ?? '投递失败'), d?.delivered === true)
    } catch (e) {
      toast('请求异常：' + String(e instanceof Error ? e.message : e), false)
    }
  }

  /** 点「我来解决」：弹窗口选择器（默认当前窗口在首，current 标记）；无候选时直接投递主窗口 */
  const openPicker = (anchor: HTMLElement, kind: 'task' | 'error', identity: SolveIdentity): void => {
    const target = deps.resolveSnapshot(kind, identity)
    if (target === null) { toast('⚠ 数据已刷新，请重试', false); return }
    close()
    const cands = deps.candidates()
    if (cands.length === 0) { void postSolve(target.kind, target.snap); return }
    const pop = document.createElement('div')
    pop.className = pf + '-solvepop'
    const head = document.createElement('div')
    head.className = pf + '-solvepop-head'
    head.textContent = '投递给窗口排查处置'
    pop.appendChild(head)
    const list = document.createElement('div')
    list.className = pf + '-solvepop-list'
    for (const c of cands) {
      const b = document.createElement('button')
      b.type = 'button'
      b.className = pf + '-solvepop-item' + (c.current ? ' cur' : '')
      b.textContent = (c.current ? '● ' : '○ ') + c.label
      b.addEventListener('click', () => { close(); void postSolve(target.kind, target.snap, c.sid) })
      list.appendChild(b)
    }
    pop.appendChild(list)
    const cancel = document.createElement('button')
    cancel.type = 'button'
    cancel.className = pf + '-solvepop-cancel'
    cancel.textContent = '取消'
    cancel.addEventListener('click', close)
    pop.appendChild(cancel)
    let hostEl: HTMLElement | undefined
    try { hostEl = typeof deps.host === 'function' ? deps.host() : deps.host } catch { hostEl = undefined }
    ;(hostEl ?? document.body).appendChild(pop)
    solvePop = pop
    // 定位：锚点下方（放不下则上方），视口内
    const rect = anchor.getBoundingClientRect()
    const popH = 40 + cands.length * 30 + 32
    let top = rect.bottom + 6
    if (top + popH > window.innerHeight) top = Math.max(6, rect.top - popH - 6)
    pop.style.position = 'fixed'
    pop.style.left = Math.min(rect.left, Math.max(6, window.innerWidth - 280)) + 'px'
    pop.style.top = top + 'px'
    // 点开后的任意外部点击关闭
    const onDoc = (ev: MouseEvent): void => {
      const t = ev.target as Element | null
      if (t !== null && pop.contains(t)) return
      document.removeEventListener('click', onDoc, true)
      solveDocClean = undefined
      close()
    }
    document.addEventListener('click', onDoc, true)
    solveDocClean = () => document.removeEventListener('click', onDoc, true)
  }

  return { toast, openPicker, close }
}
