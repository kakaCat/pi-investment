/**
 * Board styles, injected as one global stylesheet with dsh-hld- prefixed
 * classes. Surfaces/text ride the shell's --dsw-* tokens where available so
 * the board follows the active theme; status accents are the fixed palette.
 *
 * @module dashboard-holdings/client/styles
 */
export const STYLES = `
.dsh-hld-entry {
  display: flex; align-items: center; gap: 8px; position: relative;
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border: none; border-radius: 8px; background: transparent;
  color: var(--dsw-text-secondary, inherit); font: inherit; font-size: 13px;
  cursor: pointer; text-align: left;
}
.dsh-hld-entry:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-hld-entry[data-active="true"] { background: var(--dsw-active, rgba(128,128,128,.18)); color: var(--dsw-text-primary, inherit); font-weight: 500; }
.dsh-hld-entry svg { flex: none; }
/* sidebar.footer.action 列表默认按行排布——把整个 seat 容器改为纵向列，
   两个看板按钮即上下堆叠（wide 整宽 / rail 纵向图标） */
div[data-slot="sidebar.footer.action"] {
  display: flex !important; flex-direction: column; align-items: stretch; width: 100%; min-width: 0;
}
[data-sidebar-collapsed] [data-dsh-hld-entry],
[class*="_collapsed"] [data-dsh-hld-entry] {
  width: 36px; height: 36px; min-width: 36px; margin: 0 0 12px; padding: 0;
  justify-content: center; gap: 0; text-align: center;
}
[data-sidebar-collapsed] [data-dsh-hld-entry] .dsh-hld-entry-label,
[class*="_collapsed"] [data-dsh-hld-entry] .dsh-hld-entry-label { display: none; }
[data-sidebar-collapsed] [data-dsh-hld-entry] svg,
[class*="_collapsed"] [data-dsh-hld-entry] svg { width: 16px; height: 16px; }

html[data-dsh-hld-active] [data-pane="conversation"] > *:not([data-dsh-hld-view]),
html[data-dsh-hld-active] [class*="centerCol"] > *:not([data-dsh-hld-view]),
html[data-dsh-hld-active] .dshDesktopConversationSurface > *:not([data-dsh-hld-view]) { display: none !important; }
.dsh-hld-view { display: none; }
html[data-dsh-hld-active] .dsh-hld-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.dsh-hld-board { flex: 1; min-height: 0; overflow-y: auto; box-sizing: border-box; }

/* ================= 浅色监控主题（design page1，固定色板） ================= */
.dsh-hld-board {
  --panel:#fff; --line:#ebeef5; --border:#e4e7ed;
  --text:#303133; --body:#606266; --dim:#909399; --faint:#c0c4cc;
  --up:#f56c6c; --down:#67c23a; --warn:#e6a23c; --accent:#409eff;
  background:#f0f2f5; color:var(--body);
  font:13px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  padding:18px 22px 56px;
}
.dsh-hld-wrap { max-width: 1560px; }

/* 顶栏 */
.dsh-hld-topbar { display:flex; align-items:center; gap:18px; flex-wrap:wrap; margin-bottom:16px; }
.dsh-hld-topbar h1 { font-size:20px; font-weight:600; color:#1f2d3d; margin:0; letter-spacing:.3px; }
.dsh-hld-title .sub { color:var(--dim); font-size:12px; font-weight:400; margin-left:10px; }
.dsh-hld-tools { margin-left:auto; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
.dsh-hld-updated { color:var(--dim); font-size:12px; }
.dsh-hld-updated b { color:var(--body); font-weight:500; font-variant-numeric:tabular-nums; }
.dsh-hld-acct { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--dim); }
.dsh-hld-acct select {
  border:1px solid var(--border); border-radius:6px; background:var(--panel);
  color:var(--text); padding:4px 8px; font-size:12px; outline:none; cursor:pointer;
}
.dsh-hld-acct select:focus { border-color:var(--accent); }
.dsh-hld-refresh {
  background:var(--panel); color:var(--accent); border:1px solid var(--accent);
  border-radius:6px; padding:4px 14px; font-size:12px; cursor:pointer;
}
.dsh-hld-refresh:hover { background:#ecf5ff; }
.dsh-hld-refresh:active { opacity:.8; }

/* 摘要卡 */
.dsh-hld-summary { background:var(--panel); border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.05); margin-bottom:16px; overflow:hidden; }
.dsh-hld-sum-top { display:flex; align-items:center; padding:16px 20px 0; }
.dsh-hld-sum-pnl { padding:0 28px 14px 0; }
.dsh-hld-sum-pnl.right { border-left:1px solid var(--line); padding-left:28px; }
.dsh-hld-sum-pnl .n { font-size:13px; color:var(--dim); margin-bottom:4px; }
.dsh-hld-sum-pnl .v { font-size:26px; font-weight:600; color:var(--text); font-variant-numeric:tabular-nums; }
.dsh-hld-sum-pnl .v small { font-size:14px; font-weight:500; margin-left:6px; }
.dsh-hld-sum-pnl .v.up { color:var(--up); }
.dsh-hld-sum-pnl .v.down { color:var(--down); }
.dsh-hld-sum-pnl .v.flat { color:var(--body); }
.dsh-hld-sum-assets { display:grid; grid-template-columns:repeat(3,1fr); border-top:1px solid var(--line); }
.dsh-hld-sum-assets .asset-item { padding:12px 20px; }
.dsh-hld-sum-assets .asset-item + .asset-item { border-left:1px solid var(--line); }
.asset-item .n { font-size:12px; color:var(--dim); display:flex; align-items:center; gap:6px; }
.asset-item .v { font-size:18px; font-weight:600; color:var(--text); margin-top:2px; font-variant-numeric:tabular-nums; }
.legend-dot { display:inline-block; width:8px; height:8px; border-radius:50%; }

/* 合规风险行 */
.dsh-hld-risk { display:flex; flex-wrap:wrap; gap:8px; padding:12px 20px; border-top:1px solid var(--line); background:#fafbfc; }
.dsh-hld-chip { display:inline-flex; align-items:center; gap:5px; font-size:12px; padding:3px 10px; border-radius:999px; background:#f4f4f5; color:var(--body); }
.dsh-hld-chip.ok { background:#f0f9eb; color:#529b2e; }
.dsh-hld-chip.warn { background:#fdf6ec; color:var(--warn); }
.dsh-hld-chip.bad { background:#fef0f0; color:#f56c6c; }

/* 卡片 */
.dsh-hld-card { background:var(--panel); border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.05); margin-bottom:16px; overflow:hidden; }
.dsh-hld-card .hd { display:flex; align-items:baseline; justify-content:space-between; gap:12px; padding:13px 18px; border-bottom:1px solid #f0f0f0; flex-wrap:wrap; }
.dsh-hld-card .hd .t { font-size:15px; font-weight:600; color:var(--text); }
.dsh-hld-card .hd .more { font-size:12px; color:var(--dim); font-weight:400; }

/* 表格 */
.dsh-hld-card .tblwrap { overflow-x:auto; }
.dsh-hld-card table { width:100%; border-collapse:collapse; font-size:12px; min-width:760px; }
.dsh-hld-card th { text-align:left; color:var(--dim); font-weight:500; font-size:12px; padding:9px 14px; border-bottom:1px solid var(--line); background:#fafbfc; white-space:nowrap; }
.dsh-hld-card td { padding:10px 14px; border-bottom:1px solid var(--line); vertical-align:top; color:var(--body); }
.dsh-hld-card tr:last-child td { border-bottom:none; }
.dsh-hld-card th.r, .dsh-hld-card td.r { text-align:right; }
.dsh-hld-card td.r { font-variant-numeric:tabular-nums; }
.dsh-hld-card td .sub { display:block; color:var(--dim); font-size:11px; margin-top:2px; }
.dsh-hld-card .dim { color:var(--faint); font-size:11px; }
.dsh-hld-card td.up { color:var(--up); }
.dsh-hld-card td.down { color:var(--down); }

/* 名称 + 代码 */
.sec-name { color:var(--text); font-weight:500; white-space:nowrap; }
.sec-code { color:var(--faint); font-size:11px; margin-left:4px; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }

/* 买卖点参考列 */
.dsh-hld-card td.bp { line-height:1.9; }
.dsh-hld-sl { color:var(--warn); font-weight:600; white-space:nowrap; }
.dsh-hld-s { color:var(--down); white-space:nowrap; }
.dsh-hld-card td.bp .src { display:block; color:var(--faint); font-size:11px; line-height:1.6; }

/* 标签 */
.dsh-hld-tag { display:inline-block; padding:1px 8px; border-radius:4px; font-size:11px; line-height:1.7; white-space:nowrap; }
.dsh-hld-tag.buy  { background:#fef0f0; color:#f56c6c; }
.dsh-hld-tag.sell { background:#f0f9eb; color:#67c23a; }
.dsh-hld-tag.on   { background:#ecf5ff; color:#409eff; }
.dsh-hld-tag.off  { background:#f4f4f5; color:#909399; }
.dsh-hld-tag.warn, .dsh-hld-tag.trig { background:#fdf6ec; color:#e6a23c; }
.dsh-hld-tag.ok   { background:#f0f9eb; color:#529b2e; }
.dsh-hld-tag.bad  { background:#fef0f0; color:#f56c6c; }
.dsh-hld-tag.wait { background:#fdf6ec; color:#e6a23c; }

/* 盯盘中心：账户归属 tab（pill 带计数）+ 规则列表（2026-09-05 · 对齐执行看板调度任务 tab+列表） */
.dsh-hld-wtabs { display:flex; flex-wrap:wrap; gap:8px; align-items:center; padding:12px 18px 8px; border-bottom:1px solid #f0f0f0; }
.dsh-hld-wtab { appearance:none; display:inline-flex; align-items:center; gap:6px; border:1px solid var(--border); background:#fff;
  color:var(--body); font:inherit; font-size:12px; padding:3px 13px; border-radius:999px; cursor:pointer; transition:all .15s; }
.dsh-hld-wtab:hover { border-color:#b3d8ff; color:#1d6fe0; background:#f7fbff; }
.dsh-hld-wtab.act { background:#409eff; border-color:#409eff; color:#fff; font-weight:500; }
.dsh-hld-wtab .c { font-style:normal; font-weight:600; opacity:.85; font-variant-numeric:tabular-nums; }
.dsh-hld-wtabs + .tblwrap table { min-width:880px; }
.dsh-hld-auto .tblwrap table { min-width:640px; }
.dsh-hld-auto td .sub { margin-left:0; display:block; font-size:11px; }
.dsh-hld-tag.oth { background:#f4f4f5; color:#606266; }
.dsh-hld-card td.ctx { color:var(--dim); max-width:340px; }
.dsh-hld-card td.cond { color:var(--body); white-space:nowrap; }
.cond-up { color:var(--up); font-weight:600; }
.cond-down { color:var(--down); font-weight:600; }

/* 空态 */
.dsh-hld-empty { text-align:center; color:var(--dim); padding:26px 0 !important; }
.dsh-hld-emptybox { padding:30px 20px; text-align:center; color:var(--dim); font-size:13px; }

/* 错误横幅（board-mount renderError 复用） */
.dsh-hld-head { display:flex; align-items:baseline; gap:12px; margin-bottom:14px; }
.dsh-hld-title { font-size:18px; font-weight:600; color:var(--text); margin:0; }
.dsh-hld-banner { display:none; background:#fef0f0; border:1px solid #fde2e2; color:#f56c6c; padding:10px 16px; border-radius:8px; margin-bottom:14px; font-size:13px; }
.dsh-hld-banner.show { display:block; }
/* ===== 历史交易分页（dsh-hld-pg） ===== */
.dsh-hld-pg { display:flex; align-items:center; gap:8px; padding:10px 14px; border-top:1px solid #ebeef5; flex-wrap:wrap; }
.dsh-hld-pg .dsh-hld-pgb { min-width:26px; height:24px; padding:0 9px; border:1px solid #dcdfe6; border-radius:4px; background:#fff; color:#606266; font-size:12px; line-height:22px; cursor:pointer; font-family:inherit; }
.dsh-hld-pg .dsh-hld-pgb:hover:not(:disabled) { border-color:#409eff; color:#409eff; }
.dsh-hld-pg .dsh-hld-pgb:disabled { color:#c0c4cc; background:#f5f7fa; cursor:not-allowed; }
.dsh-hld-pg .dsh-hld-pgb.act { background:#409eff; border-color:#409eff; color:#fff; }
.dsh-hld-pg-nums { display:inline-flex; gap:4px; align-items:center; }
.dsh-hld-pg .gap { padding:0 2px; color:#c0c4cc; }
.dsh-hld-pg-cnt { margin-left:auto; font-size:12px; color:#909399; white-space:nowrap; }
`

/** Inject the stylesheet once (tagged for the HMR driver cleanup). */
export function injectStyles(): void {
  const id = "dsh-hld-styles"
  if (document.getElementById(id) !== null) return
  const style = document.createElement('style')
  style.id = id
  style.textContent = STYLES
  ;(document.head ?? document.documentElement).appendChild(style)
}
