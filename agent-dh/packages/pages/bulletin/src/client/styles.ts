/**
 * Bulletin client styles, injected as one global stylesheet with dsh-bbd-
 * prefixed classes. Surfaces ride the shell --dsw-* tokens where available so
 * the entry follows the active theme.
 * phase1: 顶部侧栏入口行样式。phase2（2026-09-05）：中心栏看板主体样式——
 * html[data-dsh-bbd-active] 显隐（隐藏会话列除看板外的子节点）+ .dsh-bbd-view
 * 显式 display 切换（同 holdings dsh-hld-* 显隐机制，互斥开合靠 ACTIVATE_EVENT）。
 * 色板与持仓看板同源（--dsw-* tokens + 固定状态色），仅 .dsh-bbd-* 命名空间。
 *
 * @module dashboard-bulletin/client/styles
 */
export const STYLES = `
/* ============================== 顶部侧栏入口（phase1） ============================== */
.dsh-bbd-entry {
  display: flex; align-items: center; gap: 8px; position: relative;
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border: none; border-radius: 8px; background: transparent;
  color: var(--dsw-text-secondary, inherit); font: inherit; font-size: 13px;
  cursor: pointer; text-align: left;
}
.dsh-bbd-entry:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-bbd-entry[data-active="true"] { background: var(--dsw-active, rgba(128,128,128,.18)); color: var(--dsw-text-primary, inherit); font-weight: 500; }
.dsh-bbd-entry svg { flex: none; }
[data-sidebar-collapsed] [data-dsh-bbd-entry],
[class*="_collapsed"] [data-dsh-bbd-entry] {
  width: 36px; height: 36px; min-width: 36px; margin: 0 0 12px; padding: 0;
  justify-content: center; gap: 0; text-align: center;
}
[data-sidebar-collapsed] [data-dsh-bbd-entry] .dsh-bbd-entry-label,
[class*="_collapsed"] [data-dsh-bbd-entry] .dsh-bbd-entry-label { display: none; }
[data-sidebar-collapsed] [data-dsh-bbd-entry] svg,
[class*="_collapsed"] [data-dsh-bbd-entry] svg { width: 16px; height: 16px; }

/* ============================== 中心栏看板主体（phase2） ============================== */
/* 显隐开关：会话列隐藏除本板视图外的子节点（各代 selector 都盖到） */
html[data-dsh-bbd-active] [data-pane="conversation"] > *:not([data-dsh-bbd-view]),
html[data-dsh-bbd-active] [class*="centerCol"] > *:not([data-dsh-bbd-view]),
html[data-dsh-bbd-active] .dshDesktopConversationSurface > *:not([data-dsh-bbd-view]) {
  display: none !important;
}
.dsh-bbd-view { display: none; }
html[data-dsh-bbd-active] .dsh-bbd-view {
  display: flex; flex-direction: column; height: 100%; overflow: hidden;
}

.dsh-bbd-board {
  flex: 1; min-height: 0; overflow-y: auto;
  background: #f0f2f5; padding: 18px 22px 56px;
}
.dsh-bbd-wrap { max-width: 960px; margin: 0 auto; }

/* header */
.dsh-bbd-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 6px;
}
.dsh-bbd-title { margin: 0; font-size: 19px; line-height: 1.3; color: #1f2328; }
.dsh-bbd-title .sub { margin-left: 10px; font-size: 12px; font-weight: 400; color: #8a9199; }
.dsh-bbd-tools { display: flex; align-items: center; gap: 10px; }
.dsh-bbd-chip { font-size: 12px; padding: 3px 10px; border-radius: 999px; background: #fff; border: 1px solid #e5e8ec; color: #57606a; }
.dsh-bbd-chip.warn { color: #b45309; background: #fef3c7; border-color: #fde68a; }
.dsh-bbd-chip.ok { color: #059669; background: #ecfdf5; border-color: #a7f3d0; }
.dsh-bbd-updated { font-size: 12px; color: #8a9199; }
.dsh-bbd-updated b { color: #57606a; font-weight: 600; }
.dsh-bbd-refresh {
  border: 1px solid #d0d5da; background: #fff; color: #374151;
  border-radius: 7px; padding: 4px 12px; font-size: 12px; cursor: pointer;
}
.dsh-bbd-refresh:hover { background: #f6f8fa; }

/* degraded banner（RFC D4：Agent OS 不可达显示提示而非白屏） */
.dsh-bbd-banner { display: none; }
.dsh-bbd-banner.show {
  display: block; margin: 10px 0 14px; padding: 10px 14px;
  background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412;
  border-radius: 8px; font-size: 13px; line-height: 1.6;
}

/* 过滤条 */
.dsh-bbd-filters { margin: 8px 0 14px; display: flex; flex-direction: column; gap: 8px; }
.dsh-bbd-frow { display: flex; flex-wrap: wrap; gap: 6px; }
.dsh-bbd-pill {
  display: inline-flex; align-items: center; gap: 6px;
  border: 1px solid #d0d5da; background: #fff; color: #4b5563;
  border-radius: 999px; padding: 4px 12px; font-size: 12.5px; cursor: pointer;
}
.dsh-bbd-pill:hover { border-color: #98a2b3; }
.dsh-bbd-pill.act { background: #2563eb; border-color: #2563eb; color: #fff; font-weight: 500; }
.dsh-bbd-pill i.c {
  font-style: normal; font-size: 11px; min-width: 16px; padding: 0 4px; text-align: center;
  background: rgba(0,0,0,.06); border-radius: 999px; color: inherit;
}
.dsh-bbd-pill.act i.c { background: rgba(255,255,255,.22); }
.dsh-bbd-frow.kind .dsh-bbd-pill { font-size: 12px; padding: 2px 10px; }
.dsh-bbd-frow.kind .dsh-bbd-pill.act { background: #374151; border-color: #374151; }

/* 帖子卡（单列） */
.dsh-bbd-posts { display: flex; flex-direction: column; gap: 10px; }
.dsh-bbd-post {
  display: flex; background: #fff; border: 1px solid #e5e8ec;
  border-radius: 10px; overflow: hidden; cursor: pointer;
  transition: box-shadow .12s ease;
}
.dsh-bbd-post:hover { box-shadow: 0 2px 10px rgba(17,24,39,.08); }
.dsh-bbd-bar { width: 4px; flex: none; }
.dsh-bbd-post.amber .dsh-bbd-bar { background: #f59e0b; }
.dsh-bbd-post.blue  .dsh-bbd-bar { background: #3b82f6; }
.dsh-bbd-post.red   .dsh-bbd-bar { background: #ef4444; }
.dsh-bbd-post.green .dsh-bbd-bar { background: #10b981; }
.dsh-bbd-post.gray  .dsh-bbd-bar { background: #9ca3af; }
.dsh-bbd-post.done  { opacity: .62; }
.dsh-bbd-post.dropped { opacity: .5; }
.dsh-bbd-post.dropped .dsh-bbd-title { text-decoration: line-through; color: #6b7280; }
.dsh-bbd-body { flex: 1; min-width: 0; padding: 12px 16px 11px; }

.dsh-bbd-meta-top { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.dsh-bbd-status {
  font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 999px;
}
.dsh-bbd-status.amber { color: #92400e; background: #fef3c7; }
.dsh-bbd-status.blue  { color: #1e40af; background: #dbeafe; }
.dsh-bbd-status.red   { color: #991b1b; background: #fee2e2; }
.dsh-bbd-status.green { color: #065f46; background: #d1fae5; }
.dsh-bbd-status.gray  { color: #4b5563; background: #f3f4f6; }
.dsh-bbd-kind {
  font-size: 11px; padding: 1px 8px; border-radius: 999px; border: 1px solid transparent;
}
.dsh-bbd-kind.finding  { color: #1e40af; background: #eff6ff; border-color: #bfdbfe; }
.dsh-bbd-kind.question { color: #6b21a8; background: #faf5ff; border-color: #e9d5ff; }
.dsh-bbd-kind.review   { color: #065f46; background: #ecfdf5; border-color: #a7f3d0; }
.dsh-bbd-kind.proposal { color: #9a3412; background: #fff7ed; border-color: #fed7aa; }
.dsh-bbd-badge { font-size: 11px; padding: 1px 8px; border-radius: 999px; }
.dsh-bbd-badge.bounty { color: #92400e; background: #fef3c7; border: 1px solid #fcd34d; }
.dsh-bbd-badge.stale { color: #b91c1c; background: #fff1f2; border: 1px solid #fecaca; }

.dsh-bbd-title { margin: 0 0 5px; font-size: 15px; line-height: 1.45; color: #1f2328;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.dsh-bbd-content { color: #4b5563; font-size: 13px; line-height: 1.65; white-space: pre-wrap; word-break: break-word;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.dsh-bbd-post.exp .dsh-bbd-title, .dsh-bbd-post.exp .dsh-bbd-content { display: block; -webkit-line-clamp: unset; }
.dsh-bbd-drop { margin-top: 6px; font-size: 12px; color: #b91c1c; }
.dsh-bbd-log { display: none; margin-top: 10px; padding: 8px 10px; background: #f9fafb;
  border-radius: 6px; border: 1px solid #eef0f3; font-size: 12px; }
.dsh-bbd-post.exp .dsh-bbd-log { display: block; }
.dsh-bbd-log-hd { color: #6b7280; font-weight: 600; margin-bottom: 5px; }
.dsh-bbd-log-row { color: #4b5563; line-height: 1.7; }
.dsh-bbd-log-row b { color: #1f2328; }
.dsh-bbd-meta {
  margin-top: 10px; padding-top: 8px; border-top: 1px dashed #eceef1;
  font-size: 12px; color: #8a9199; line-height: 1.7;
}
.dsh-bbd-meta b { color: #57606a; font-weight: 600; }
.dsh-bbd-meta .dim { color: #b6bcc3; }

.dsh-bbd-emptybox {
  padding: 46px 20px; text-align: center; color: #8a9199; font-size: 13px;
  background: #fff; border: 1px dashed #d0d5da; border-radius: 10px;
}

/* 分页 */
.dsh-bbd-pg {
  display: flex; align-items: center; gap: 8px; margin-top: 16px; flex-wrap: wrap;
}
.dsh-bbd-pgnav, .dsh-bbd-pgb {
  border: 1px solid #d0d5da; background: #fff; color: #374151;
  border-radius: 6px; padding: 3px 10px; font-size: 12px; cursor: pointer;
}
.dsh-bbd-pgnav:disabled, .dsh-bbd-pgb:disabled { opacity: .45; cursor: default; }
.dsh-bbd-pgb.act { background: #2563eb; border-color: #2563eb; color: #fff; }
.dsh-bbd-pg-nums { display: inline-flex; gap: 5px; }
.dsh-bbd-pg-cnt { margin-left: auto; font-size: 12px; color: #8a9199; }
.dsh-bbd-rangenote { margin-top: 4px; text-align: right; font-size: 11.5px; color: #b6bcc3; }

/* Task #2：认领/转交动作行 + 转交选择器 + toast */
.dsh-bbd-acts {
  margin-top: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.dsh-bbd-btn {
  border: 1px solid #d0d5da; background: #fff; color: #374151;
  border-radius: 6px; padding: 3px 12px; font-size: 12px; cursor: pointer; line-height: 1.5;
}
.dsh-bbd-btn:hover:not(:disabled) { border-color: #2563eb; color: #2563eb; }
.dsh-bbd-btn:disabled { opacity: .5; cursor: default; }
.dsh-bbd-btn.solve { background: #2563eb; border-color: #2563eb; color: #fff; }
.dsh-bbd-btn.solve:hover:not(:disabled) { background: #1d4ed8; color: #fff; }
.dsh-bbd-btn.delegate { background: #f9fafb; }
.dsh-bbd-acts-hint { font-size: 11px; color: #b6bcc3; }
.dsh-bbd-pick {
  margin-top: 8px; padding: 8px 10px; background: #f6f8fa; border: 1px solid #e2e6ea;
  border-radius: 8px;
}
.dsh-bbd-pick-hd {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  font-size: 12px; color: #374151; margin-bottom: 6px;
}
.dsh-bbd-pick-close {
  border: none; background: transparent; color: #8a9199; cursor: pointer; font-size: 12px; padding: 0 2px;
}
.dsh-bbd-pick-close:hover { color: #b91c1c; }
.dsh-bbd-pick-list { display: flex; flex-direction: column; gap: 4px; max-height: 180px; overflow-y: auto; }
.dsh-bbd-picksession {
  text-align: left; border: 1px solid #d0d5da; background: #fff; color: #374151;
  border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer;
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.dsh-bbd-picksession:hover { border-color: #2563eb; color: #2563eb; }
.dsh-bbd-picksession.cur { border-color: #93c5fd; background: #eff6ff; }
.dsh-bbd-picksession i {
  font-style: normal; font-size: 10.5px; color: #2563eb; background: #dbeafe;
  padding: 0 6px; border-radius: 999px;
}
.dsh-bbd-pick-empty { font-size: 12px; color: #8a9199; }
.dsh-bbd-toast {
  position: fixed; top: 14px; right: 16px; z-index: 9999; max-width: min(420px, 70vw);
  padding: 9px 14px; border-radius: 8px; font-size: 13px; line-height: 1.55;
  box-shadow: 0 6px 22px rgba(15, 23, 42, .16); opacity: 1;
  transition: opacity .35s ease; word-break: break-word;
}
.dsh-bbd-toast.ok { background: #065f46; color: #ecfdf5; border: 1px solid #34d399; }
.dsh-bbd-toast.err { background: #7f1d1d; color: #fef2f2; border: 1px solid #f87171; }
.dsh-bbd-toast.out { opacity: 0; }
`

/** Inject the stylesheet once (tagged for the HMR driver cleanup). */
export function injectStyles(): void {
  const id = 'dsh-bbd-styles'
  if (document.getElementById(id) !== null) return
  const style = document.createElement('style')
  style.id = id
  style.textContent = STYLES
  ;(document.head ?? document.documentElement).appendChild(style)
}
