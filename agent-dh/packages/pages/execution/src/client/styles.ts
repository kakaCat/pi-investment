/**
 * Board styles, injected as one global stylesheet with dsh-exec- prefixed
 * classes. Surfaces/text ride the shell's --dsw-* tokens where available so
 * the board follows the active theme; status accents are the fixed palette.
 *
 * @module dashboard-execution/client/styles
 */
export const STYLES = `
.dsh-exec-entry {
  display: flex; align-items: center; gap: 8px; position: relative;
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border: none; border-radius: 8px; background: transparent;
  color: var(--dsw-text-secondary, inherit); font: inherit; font-size: 13px;
  cursor: pointer; text-align: left;
}
.dsh-exec-entry:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-exec-entry[data-active="true"] { background: var(--dsw-active, rgba(128,128,128,.18)); color: var(--dsw-text-primary, inherit); font-weight: 500; }
.dsh-exec-entry svg { flex: none; }
[data-sidebar-collapsed] [data-dsh-exec-entry],
[class*="_collapsed"] [data-dsh-exec-entry] {
  width: 36px; height: 36px; min-width: 36px; margin: 0 0 12px; padding: 0;
  justify-content: center; gap: 0; text-align: center;
}
[data-sidebar-collapsed] [data-dsh-exec-entry] .dsh-exec-entry-label,
[class*="_collapsed"] [data-dsh-exec-entry] .dsh-exec-entry-label { display: none; }
[data-sidebar-collapsed] [data-dsh-exec-entry] svg,
[class*="_collapsed"] [data-dsh-exec-entry] svg { width: 16px; height: 16px; }

html[data-dsh-exec-active] [data-pane="conversation"] > *:not([data-dsh-exec-view]),
html[data-dsh-exec-active] [class*="centerCol"] > *:not([data-dsh-exec-view]),
html[data-dsh-exec-active] .dshDesktopConversationSurface > *:not([data-dsh-exec-view]) { display: none !important; }
.dsh-exec-view { display: none; }
html[data-dsh-exec-active] .dsh-exec-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.dsh-exec-board { flex: 1; min-height: 0; overflow-y: auto; box-sizing: border-box; }

/* ---- board inner ---- */
.dsh-exec-board {
  --bg:#0b0f1c; --panel:#121a2c; --panel2:#0f1626; --line:#1e2a44;
  --text:#dbe4f0; --dim:#8ea0bd; --faint:#5b6b8c;
  --ok:#22c55e; --fail:#ef4444; --late:#eab308; --pend:#94a3b8;
  --unk:#a855f7; --off:#4b5563; --deg:#f97316; --accent:#3b82f6;
  padding: 14px 18px 40px; color: var(--text); font: 13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
}
body[data-ds-dark-theme] .dsh-exec-board { --text:#e6e8eb; --dim:#9aa3b2; --faint:#6a7385; --line:#333947; --panel:#20242e; --panel2:#1a1e27; --bg:#14161d; }
.dsh-exec-board * { box-sizing: border-box; }
.dsh-exec-wrap { max-width: 1560px; }
.dsh-exec-head { display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }
.dsh-exec-title { font-size: 18px; letter-spacing: .5px; margin: 0; color: var(--text); }
.dsh-exec-title small { color: var(--faint); font-weight: normal; margin-left: 10px; font-size: 11px; }
.dsh-exec-meta { margin-left: auto; color: var(--faint); font-size: 12px; display: flex; gap: 14px; align-items: baseline; }
.dsh-exec-btn { background: var(--accent); color: #fff; border: 0; border-radius: 6px; padding: 5px 14px; font-size: 12px; cursor: pointer; }
.dsh-exec-btn:active { opacity: .8; }
.dsh-exec-legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11px; color: var(--dim); align-items: center; }
.dsh-exec-lg { display: inline-flex; align-items: center; gap: 4px; }
.dsh-exec-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }
.dsh-exec-banner { display: none; background:#3b1c1c; border:1px solid var(--fail); color:#fca5a5; padding:8px 14px; border-radius:8px; margin-bottom:14px; font-size:12px; }
.dsh-exec-banner.show { display:block; }
.dsh-exec-sec { margin-bottom: 20px; }
.dsh-exec-sec > h2 { font-size: 13px; color: var(--accent); border-left: 3px solid var(--accent); padding-left: 8px; margin: 0 0 8px; }
.dsh-exec-sec > h2 .sub { color: var(--faint); font-weight: normal; font-size: 10.5px; margin-left: 8px; }
.dsh-exec-grid4 { display: grid; grid-template-columns: repeat(auto-fit,minmax(230px,1fr)); gap: 10px; }
.dsh-exec-card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }
.dsh-exec-card h3 { font-size: 13px; display: flex; align-items: center; gap: 8px; margin: 0 0 8px; }
.dsh-exec-card h3 .port { color: var(--faint); font-weight: normal; font-size: 11px; }
.dsh-exec-kv { color: var(--dim); font-size: 11.5px; }
.dsh-exec-kv div { display: flex; justify-content: space-between; gap: 8px; }
.dsh-exec-kv b { color: var(--text); font-weight: 500; text-align: right; word-break: break-all; }
.dsh-exec-errline { color: #fca5a5; font-size: 11px; margin-top: 6px; word-break: break-all; }
.dsh-exec-time { color: var(--faint); font-size: 10.5px; margin-top: 6px; }
.dsh-exec-ok, .dsh-exec-confirmed { color: var(--ok); }
.dsh-exec-fail, .dsh-exec-failed { color: var(--fail); }
.dsh-exec-late { color: var(--late); }
.dsh-exec-pending { color: var(--pend); }
.dsh-exec-unknown { color: var(--unk); }
.dsh-exec-degraded { color: var(--deg); }
.dsh-exec-off_day { color: var(--off); }
.dsh-exec-dot.ok, .dsh-exec-dot.confirmed { background: var(--ok); }
.dsh-exec-dot.failed { background: var(--fail); }
.dsh-exec-dot.late { background: var(--late); }
.dsh-exec-dot.pending { background: var(--pend); }
.dsh-exec-dot.unknown { background: var(--unk); }
.dsh-exec-dot.off_day { background: var(--off); }
.dsh-exec-dot.degraded { background: var(--deg); }
.dsh-exec-alert-card { background: #261818; border: 1px solid #7f1d1d; border-radius: 10px; padding: 12px 14px; }
.dsh-exec-alert-item { display:flex; gap:10px; align-items:baseline; margin-bottom:6px; font-size:12px; }
.dsh-exec-alert-item .flow { color: var(--faint); }
.dsh-exec-cp-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(196px,1fr)); gap:8px; }
.dsh-exec-cp { background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--line); border-radius:8px; padding:9px 11px; }
.dsh-exec-cp .top { display:flex; justify-content:space-between; align-items:center; gap:6px; }
.dsh-exec-cp .mod { font-size:10px; color:var(--faint); }
.dsh-exec-cp .nm { font-size:12.5px; margin:3px 0; }
.dsh-exec-cp .msg { font-size:11px; color:var(--dim); word-break:break-all; }
.dsh-exec-group-title { font-size:11px; color:var(--faint); margin:12px 0 6px; letter-spacing:1px; }
.dsh-exec-errs { list-style:none; margin:0; padding:0; }
.dsh-exec-errs li { font-family: ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11px; padding:6px 10px; border-bottom:1px solid var(--line); display:flex; gap:10px; align-items:baseline; color:var(--dim); }
.dsh-exec-errs li .src { flex:none; border-radius:4px; padding:0 6px; font-size:10px; }
.dsh-exec-errs .src.v2 { background:#3b2a14; color:#fbbf24; }
.dsh-exec-errs .src.os { background:#10293f; color:#60a5fa; }
.dsh-exec-errs .src.dsh { background:#3b1140; color:#d8b4fe; }
.dsh-exec-errs .line { color:#e2e8f0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:70%; }
.dsh-exec-errs .file { color:var(--faint); flex:none; }
.dsh-exec-timeline { display:flex; flex-wrap:wrap; gap:6px; }
.dsh-exec-tl { border:1px solid var(--line); background:var(--panel2); border-radius:8px; padding:5px 10px; font-size:11.5px; display:flex; gap:8px; align-items:center; }
.dsh-exec-tl .t { color:var(--accent); font-weight:600; }
.dsh-exec-tl .e { color:var(--dim); }
.dsh-exec-table { width:100%; border-collapse:collapse; font-size:12px; background:var(--panel); border-radius:10px; }
.dsh-exec-table th { text-align:left; color:var(--faint); font-weight:500; padding:8px 10px; border-bottom:1px solid var(--line); background:var(--panel2); font-size:11px; white-space:nowrap; }
.dsh-exec-table td { padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; color:var(--text); }
.dsh-exec-table td.num, .dsh-exec-table td.id { color:var(--faint); white-space:nowrap; }
.dsh-exec-table td.err { font-family:ui-monospace,Consolas,monospace; font-size:10.5px; color:#fca5a5; word-break:break-all; }
.dsh-exec-dim { color:var(--dim); } .dsh-exec-faint { color:var(--faint); }
.dsh-exec-on { color:var(--ok); } .dsh-exec-off { color:var(--fail); }
.dsh-exec-empty { color: var(--faint); font-size: 12px; padding: 8px 0; }
`

/** Inject the stylesheet once (tagged for the HMR driver's cleanup). */
export function injectStyles(): void {
  const id = 'dsh-exec-styles'
  if (document.getElementById(id) !== null) return
  const style = document.createElement('style')
  style.id = id
  style.textContent = STYLES
  ;(document.head ?? document.documentElement).appendChild(style)
}
