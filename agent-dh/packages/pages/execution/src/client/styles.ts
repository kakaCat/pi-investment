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
/* sidebar.footer.action 列表默认按行排布——把整个 seat 容器改为纵向列，
   两个看板按钮即上下堆叠（wide 整宽 / rail 纵向图标） */
div[data-slot="sidebar.footer.action"] {
  display: flex !important; flex-direction: column; align-items: stretch; width: 100%; min-width: 0;
}
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

/* ================= 浅色监控主题（design page2，固定色板） ================= */
.dsh-exec-board {
  --panel:#fff; --line:#ebeef5; --border:#e4e7ed;
  --text:#303133; --body:#606266; --dim:#909399; --faint:#c0c4cc;
  --ok:#67c23a; --bad:#f56c6c; --late:#e6a23c; --wait:#909399; --unk:#a2a8b3;
  background:#f0f2f5; color:var(--body);
  font:13px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  padding:18px 22px 56px;
}
.dsh-exec-board * { box-sizing: border-box; }
.dsh-exec-wrap { max-width: 1560px; }

/* 顶栏 */
.dsh-exec-head { display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:16px; }
.dsh-exec-title { font-size:20px; font-weight:600; color:#1f2d3d; margin:0; letter-spacing:.3px; }
.dsh-exec-title small { color:var(--dim); font-size:12px; font-weight:400; margin-left:10px; }
.dsh-exec-meta { margin-left:auto; display:flex; align-items:center; gap:14px; color:var(--dim); font-size:12px; }
.dsh-exec-last { font-variant-numeric:tabular-nums; }
.dsh-exec-btn { background:var(--panel); color:var(--accent, #409eff); border:1px solid var(--accent, #409eff); border-radius:6px; padding:4px 14px; font-size:12px; cursor:pointer; }
.dsh-exec-btn:hover { background:#ecf5ff; }
.dsh-exec-btn:active { opacity:.8; }
.dsh-exec-banner { display:none; background:#fef0f0; border:1px solid #fde2e2; color:#f56c6c; padding:10px 16px; border-radius:8px; margin-bottom:14px; font-size:13px; }
.dsh-exec-banner.show { display:block; }

/* 区块卡 */
.dsh-exec-cardx { background:var(--panel); border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.05); margin-bottom:16px; overflow:hidden; }
.dsh-exec-cardx .hd { display:flex; align-items:baseline; justify-content:space-between; gap:12px; padding:13px 18px; border-bottom:1px solid #f0f0f0; flex-wrap:wrap; }
.dsh-exec-cardx .hd .t { font-size:15px; font-weight:600; color:var(--text); }
.dsh-exec-cardx .hd .more { font-size:12px; color:var(--dim); font-weight:400; }
.dsh-exec-cardx .bd { padding:14px 18px; }
.dsh-exec-empty { color:var(--faint); font-size:13px; padding:10px 0; }
/* 分类对账提示（2026-09-12）：字段未打通 / 未归类任务 / OS 并入对账 —— 显式可见，不静默 */
.dsh-exec-cover { display:flex; flex-wrap:wrap; gap:6px 14px; padding:6px 0 8px; font-size:12px; color:var(--faint); }
.dsh-exec-cover span { padding:2px 8px; border-radius:4px; background:var(--bg2); }
.dsh-exec-cover code { font-family:var(--mono, monospace); padding:0 3px; }

/* 执行总览：大数字健康条 + 服务 pills */
.dsh-exec-hb { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:12px; }
.hb-item { border-radius:10px; padding:12px 16px; text-align:center; background:#fafbfc; border:1px solid var(--line); }
.hb-item .v { font-size:30px; font-weight:700; color:var(--text); font-variant-numeric:tabular-nums; line-height:1.2; }
.hb-item .n { font-size:12px; color:var(--dim); margin-top:3px; }
.hb-item.ok { background:#f0f9eb; border-color:#e1f3d8; } .hb-item.ok .v { color:#67c23a; }
.hb-item.bad { background:#fef0f0; border-color:#fde2e2; } .hb-item.bad .v { color:#f56c6c; }
.hb-item.wait { background:#f4f4f5; border-color:#ebeef5; } .hb-item.wait .v { color:#909399; }
.dsh-exec-pills { display:flex; flex-wrap:wrap; gap:8px; }
.dsh-exec-pills .pill { display:inline-flex; align-items:center; gap:6px; font-size:12px; padding:4px 12px; border-radius:999px; background:#f4f4f5; color:var(--body); }
.dsh-exec-pills .pill.ok { background:#f0f9eb; color:#529b2e; }
.dsh-exec-pills .pill.warn { background:#fdf6ec; color:#e6a23c; }
.dsh-exec-pills .pill b { font-weight:500; }
.dsh-exec-pills .dot { width:8px; height:8px; border-radius:50%; background:var(--wait); }
.dsh-exec-pills .dot.ok { background:#67c23a; } .dsh-exec-pills .dot.bad { background:#f56c6c; }
.dsh-exec-pills .dot.deg { background:#e6a23c; } .dsh-exec-pills .dot.unk { background:#c0c4cc; }

/* 流水线带：ENGINE × AUTONOMY */
.dsh-exec-band { margin-bottom:16px; }
.dsh-exec-band:last-child { margin-bottom:0; }
.band-t { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.band-badge { font-size:10px; letter-spacing:1px; padding:2px 8px; border-radius:4px; font-weight:600; }
.band-badge.engine { background:#ecf5ff; color:#409eff; }
.band-badge.autonomy { background:#fdf6ec; color:#e6a23c; }
.band-t i { flex:1; height:1px; background:var(--line); }
.band-nodes { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:8px; }
.dsh-exec-band .node { background:#fff; border:1px solid var(--line); border-left:3px solid var(--wait); border-radius:8px; padding:9px 11px; min-width:0; }
.dsh-exec-band .node.st-ok { border-left-color:#67c23a; }
.dsh-exec-band .node.st-bad { border-left-color:#f56c6c; }
.dsh-exec-band .node.st-late, .dsh-exec-band .node.st-deg { border-left-color:#e6a23c; }
.dsh-exec-band .node .n-top { display:flex; align-items:center; gap:6px; }
.dsh-exec-band .node .n-top b { font-size:12px; color:var(--text); font-weight:600; }
.dsh-exec-band .node .n-top span { font-size:12.5px; color:var(--text); font-weight:500; margin-right:auto; }
.dsh-exec-band .node .n-top em { font-style:normal; font-size:11px; color:var(--dim); white-space:nowrap; }
.dsh-exec-band .node .dot { width:8px; height:8px; border-radius:50%; flex:none; background:var(--wait); }
.dsh-exec-band .node .dot.ok { background:#67c23a; } .dsh-exec-band .node .dot.bad { background:#f56c6c; }
.dsh-exec-band .node .dot.late, .dsh-exec-band .node .dot.deg { background:#e6a23c; }
.dsh-exec-band .node .dot.off, .dsh-exec-band .node .dot.unk { background:#c0c4cc; }
.dsh-exec-band .node .cps { list-style:none; margin:7px 0 0; padding:0; border-top:1px dashed var(--line); }
.dsh-exec-band .node .cps li { display:flex; align-items:center; gap:6px; font-size:11.5px; color:var(--body); padding-top:5px; }
.dsh-exec-band .node .cps li .dot { width:6px; height:6px; }
.dsh-exec-band .node .cps li em { font-style:normal; color:var(--faint); margin-left:auto; font-size:10.5px; white-space:nowrap; }
.dsh-exec-band .node .cps li.cp-empty { color:var(--faint); }
.dsh-exec-band .node .cps li time.cp-tm { flex:none; min-width:36px; text-align:center; font-size:10px; line-height:1.7; color:var(--faint); background:#f4f4f5; border-radius:3px; padding:0 4px; font-variant-numeric:tabular-nums; }

/* 今日时间轴：日执行 / 周执行 分组（2026-09-04） */
.dsh-exec-tlg + .dsh-exec-tlg { margin-top:16px; }
.dsh-exec-tlg .tlg-t { display:flex; align-items:baseline; gap:8px; margin-bottom:6px; }
.dsh-exec-tlg .tlg-t .t { font-size:12.5px; font-weight:600; color:var(--text); }
.dsh-exec-tlg .tlg-t .t::before { content:''; display:inline-block; width:8px; height:8px; border-radius:2px; margin-right:7px; background:#409eff; vertical-align:0; }
.dsh-exec-tlg + .dsh-exec-tlg .tlg-t .t::before { background:#e6a23c; }
.dsh-exec-tlg .tlg-t em { font-style:normal; font-size:11px; color:var(--faint); margin-left:auto; }
.dsh-exec-tlg .dsh-exec-tl-list { border:1px solid var(--line); border-radius:8px; padding:2px 12px; background:#fff; }
/* 业务线分组着色（2026-09-08：引擎蓝 / Autonomy 紫） */
.dsh-exec-tlg.t-engine .tlg-t .t::before { background:#409eff; }
.dsh-exec-tlg.t-autonomy .tlg-t .t::before { background:#9c6ade; }
/* 非双线（账户 / 其它）折叠组（2026-09-08：默认收起，展示条目计数） */
.dsh-exec-tld { margin-top:16px; border:1px dashed var(--line); border-radius:8px; background:#fbfcfe; }
.dsh-exec-tld + .dsh-exec-tld { margin-top:8px; }
.dsh-exec-tld summary { display:flex; align-items:center; gap:7px; list-style:none; cursor:pointer; padding:7px 12px; font-size:12px; color:var(--dim); user-select:none; }
.dsh-exec-tld summary::-webkit-details-marker { display:none; }
.dsh-exec-tld summary .caret { transition:transform .12s; color:var(--faint); font-size:9px; flex:none; }
.dsh-exec-tld[open] summary .caret { transform:rotate(90deg); }
.dsh-exec-tld summary b { font-weight:600; font-size:12.5px; color:var(--text); }
.dsh-exec-tld summary em { font-style:normal; font-size:11px; color:var(--faint); margin-left:auto; white-space:nowrap; }
.dsh-exec-tld .dsh-exec-tl-list { border:none; background:transparent; padding:0 6px 4px 10px; }

/* 时间轴 */
.dsh-exec-tl-list { position:relative; }
.dsh-exec-tl-list::before { content:''; position:absolute; left:106px; top:6px; bottom:6px; width:2px; background:var(--line); border-radius:1px; }
.tl-item { position:relative; display:flex; align-items:center; gap:12px; padding:8px 0; }
.tl-item .tl-tm { flex:none; width:72px; text-align:right; font-size:12px; color:var(--faint); font-variant-numeric:tabular-nums; }
.tl-item .tl-ic { flex:none; width:18px; text-align:center; font-size:13px; }
.tl-item .tl-bd { display:flex; align-items:baseline; gap:10px; min-width:0; flex:1; }
.tl-item .tl-nm { font-size:13px; color:var(--text); }
.tl-item .tl-st { flex:none; font-size:11px; padding:0 8px; border-radius:4px; line-height:1.8; }
.tl-item.ok .tl-st { background:#f0f9eb; color:#529b2e; }
.tl-item.bad .tl-st { background:#fef0f0; color:#f56c6c; }
.tl-item.wait .tl-st { background:#f4f4f5; color:#909399; }
.tl-item.unk .tl-st { background:#f4f4f5; color:#a2a8b3; }
.tl-item.off .tl-st { background:#f4f4f5; color:#a2a8b3; }
.tl-item.off .tl-nm { color:#909399; }
.tl-item.bad .tl-nm { color:#f56c6c; }
.tl-item.bad { background:#fff5f5; border-radius:8px; padding:8px 10px; margin:0 -10px; }
/* 徽标：调度来源 v2/os · 调用 agent dh/ts（时间轴行尾 + 任务表） */
.tl-item .tl-tags { margin-left:auto; display:inline-flex; align-items:center; gap:4px; flex:none; }
.exec-chip { display:inline-block; font:600 9.5px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; padding:0 4px; border-radius:3px; vertical-align:1px; white-space:nowrap; }
.exec-chip.src.v2 { background:#e8f1fd; color:#3370c9; }
.exec-chip.src.os { background:#fdf3e3; color:#d98c1f; }
.exec-chip.ag.dh { background:#f3ecfa; color:#8b5fc8; }
.exec-chip.ag.ts { background:#e0f4f6; color:#1498a8; }

/* 任务分组 */
.dsh-exec-domain { margin-bottom:14px; }
.dsh-exec-domain:last-child { margin-bottom:0; }
.dm-t { display:flex; align-items:baseline; gap:8px; margin-bottom:6px; }
.dm-t .t { font-size:13px; font-weight:600; color:var(--text); }
.dm-t em { font-style:normal; font-size:11px; color:var(--faint); }
.dm-rows { border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.tk-row { display:flex; align-items:center; gap:12px; padding:7px 12px; font-size:12.5px; }
.tk-row + .tk-row { border-top:1px solid var(--line); }
.tk-row:hover { background:#fafbfc; }
.tk-nm { color:var(--text); }
.tk-tg { flex:none; }
.tk-tm { margin-left:auto; color:var(--faint); font-size:11px; font-variant-numeric:tabular-nums; white-space:nowrap; }
.dsh-exec-domain .tag, .dsh-exec-block .tag { display:inline-block; padding:0 8px; border-radius:4px; font-size:11px; line-height:1.8; white-space:nowrap; }
.dsh-exec-domain .tag.ok, .dsh-exec-block .tag.ok { background:#f0f9eb; color:#529b2e; }
.dsh-exec-domain .tag.bad, .dsh-exec-block .tag.bad { background:#fef0f0; color:#f56c6c; }
.dsh-exec-domain .tag.wait, .dsh-exec-block .tag.wait { background:#f4f4f5; color:#909399; }
.dsh-exec-domain .tag.off { background:#f4f4f5; color:#909399; }


/* 调度任务：任务卡 tab 横排 + 点击详情（2026-09-04） */
.dsh-exec-tks { display:flex; flex-wrap:wrap; gap:10px; }
.dsh-exec-tk { appearance:none; display:flex; flex-direction:column; gap:3px; flex:0 0 auto; min-width:176px; max-width:272px;
  padding:8px 12px 7px; border:1px solid var(--line); border-radius:10px; background:#fff;
  font:inherit; color:var(--text); cursor:pointer; text-align:left; position:relative; overflow:hidden;
  transition:border-color .15s, box-shadow .15s, transform .1s; }
.dsh-exec-tk::before { content:''; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--wait); }
.dsh-exec-tk.st-ok::before { background:#67c23a; }
.dsh-exec-tk.st-bad::before { background:#f56c6c; }
.dsh-exec-tk.st-wait::before { background:#e6a23c; }
.dsh-exec-tk.st-off::before, .dsh-exec-tk.st-unk::before { background:#c0c4cc; }
.dsh-exec-tk:hover { border-color:#b3d8ff; box-shadow:0 2px 6px rgba(64,158,255,.14); }
.dsh-exec-tk.sel { border-color:#409eff; box-shadow:0 0 0 2px rgba(64,158,255,.16); background:#f7fbff; }
.dsh-exec-tk.sel .tk-name { color:#1d6fe0; }
.dsh-exec-tk .tk-top { display:flex; align-items:center; gap:6px; min-width:0; }
.dsh-exec-tk .tk-name { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:600; font-size:13px; color:var(--text); }
.dsh-exec-tk .tk-tag { flex:none; }
.dsh-exec-tk .tk-cap { color:var(--dim); font-size:11px; font-variant-numeric:tabular-nums; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.dk { width:8px; height:8px; border-radius:50%; flex:none; background:#909399; }
.dk.d0 { background:#409eff; } .dk.d1 { background:#67c23a; } .dk.d2 { background:#e6a23c; }
.dk.d3 { background:#9c6ade; } .dk.d4 { background:#26c6da; } .dk.d5 { background:#ff7a45; }
.dk.d6 { background:#00b578; } /* 自主例程（Agent OS 调 agent） */
.dk.dx { background:#a2a8b3; }
/* 业务线配色（2026-09-08：tab 圆点 / 时间轴折叠组 / 任务行线标 共用） */
.dk.l-engine { background:#409eff; } .dk.l-autonomy { background:#9c6ade; }
.dk.l-account { background:#26c6da; } .dk.l-other { background:#a2a8b3; }
.dsh-exec-legend { display:flex; align-items:center; gap:16px; flex-wrap:wrap; padding:0 0 10px; font-size:12px; color:var(--dim); }
.dsh-exec-legend .lg { display:inline-flex; align-items:center; gap:5px; }
.dsh-exec-legend .lg b { color:var(--text); font-weight:600; font-variant-numeric:tabular-nums; }
.dsh-exec-hint { margin-left:auto; color:var(--faint); font-size:11px; display:inline-flex; align-items:center; gap:5px; flex-wrap:wrap; }
.dsh-exec-hint .dot { width:7px; height:7px; border-radius:50%; display:inline-block; }
.dsh-exec-hint .dot.ok { background:#67c23a; } .dsh-exec-hint .dot.bad { background:#f56c6c; }
.dsh-exec-hint .dot.wait { background:#e6a23c; } .dsh-exec-hint .dot.off { background:#c0c4cc; }
.dsh-exec-tkdetail { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px 22px; margin-top:12px;
  background:#fafbfc; border:1px solid var(--line); border-left:3px solid #409eff; border-radius:10px; padding:11px 16px; }
.dsh-exec-tkdetail .tkd-i { min-width:0; }
.dsh-exec-tkdetail .tkd-i b { display:block; font-weight:600; font-size:11px; color:var(--faint); margin-bottom:1px; }
.dsh-exec-tkdetail .tkd-i span { font-size:12.5px; color:var(--text); word-break:break-all; }
.dsh-exec-tkdetail .tkd-code { font-style:normal; color:var(--faint); font-size:11px; margin-left:6px; }
.dsh-exec-tkdetail .tkd-err { grid-column:1 / -1; }
.dsh-exec-tkdetail .tkd-err span { color:#f56c6c; }
.dsh-exec-tkdetail .tag { display:inline-block; padding:0 8px; border-radius:4px; font-size:11px; line-height:1.8; }


/* 调度任务：分类 tab（pill，带计数）+ 任务表格（2026-09-04 v2 · 对齐设计稿定时任务表） */
.dsh-exec-tabs { display:flex; flex-wrap:wrap; gap:8px; align-items:center; padding:0 0 12px; }
.dsh-exec-tab { appearance:none; display:inline-flex; align-items:center; gap:5px; border:1px solid var(--line); background:#fff;
  color:var(--body); font:inherit; font-size:12.5px; padding:4px 13px; border-radius:999px; cursor:pointer; transition:all .15s; }
.dsh-exec-tab:hover { border-color:#b3d8ff; color:#1d6fe0; background:#f7fbff; }
.dsh-exec-tab.act { background:#409eff; border-color:#409eff; color:#fff; font-weight:500; }
.dsh-exec-tab .c { font-weight:600; opacity:.8; font-variant-numeric:tabular-nums; }
.dsh-exec-tab .dk { width:7px; height:7px; flex:none; }
.dsh-exec-legend2 { padding:0 0 2px; }
.dsh-exec-tbwrap { overflow-x:auto; border:1px solid var(--line); border-radius:8px; }
.dsh-exec-tb { width:100%; border-collapse:collapse; font-size:12.5px; background:#fff; }
.dsh-exec-tb th { text-align:left; color:var(--dim); font-weight:500; font-size:11.5px; padding:7px 12px; border-bottom:1px solid var(--line); background:#fafbfc; white-space:nowrap; }
.dsh-exec-tb td { padding:7px 12px; border-bottom:1px solid #f5f5f5; color:var(--body); vertical-align:middle; }
.dsh-exec-tb tbody tr:last-child td { border-bottom:none; }
.dsh-exec-tb tbody tr { cursor:pointer; }
.dsh-exec-tb tbody tr:hover { background:#f7fbff; }
.dsh-exec-tb tbody tr.sel { background:#ecf5ff; }
.dsh-exec-tb tbody tr.sel td { color:var(--text); }
.dsh-exec-tb tr.empty { cursor:default; text-align:center; color:var(--faint); }
.dsh-exec-tb .nm .ln-hd { display:inline-flex; align-items:center; gap:5px; }
.dsh-exec-tb .nm .ln-hd .dk { width:7px; height:7px; }
.dsh-exec-tb .nm .zh { color:var(--text); font-weight:500; }
.dsh-exec-tb .nm .code { display:block; color:var(--faint); font-size:10.5px; margin-top:1px; }
.dsh-exec-tb .cr { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11.5px; color:var(--dim); white-space:nowrap; }
.dsh-exec-tb .tag { display:inline-block; padding:0 8px; border-radius:4px; font-size:11px; line-height:1.8; white-space:nowrap; }
.dsh-exec-tb .tag.ok { background:#f0f9eb; color:#529b2e; }
.dsh-exec-tb .tag.bad { background:#fef0f0; color:#f56c6c; }
.dsh-exec-tb .tag.wait { background:#f4f4f5; color:#909399; }
.dsh-exec-tb .tag.off { background:#f4f4f5; color:#a2a8b3; }
.dsh-exec-tb .ls { font-style:normal; font-size:10.5px; margin-left:5px; color:var(--dim); }
.dsh-exec-tb .ls.ok { color:#67c23a; } .dsh-exec-tb .ls.bad { color:#f56c6c; }
.dsh-exec-tb .ls.wait { color:#e6a23c; } .dsh-exec-tb .ls.unk { color:var(--faint); }
.dsh-exec-tb .tm, .dsh-exec-tb .nx, .dsh-exec-tb .td { white-space:nowrap; font-variant-numeric:tabular-nums; }
.dsh-exec-tb .st { white-space:nowrap; }
.dsh-exec-tb .st .exec-chip { margin-left:5px; }
.dsh-exec-tb .tm, .dsh-exec-tb .nx { color:var(--dim); font-size:12px; }
.dsh-exec-tb .td { color:var(--body); font-size:12px; }

/* 调度任务：一体卡片 + 表底分页条（2026-09-05 v2 · 观感对齐 holdings「历史交易」分页） */
.dsh-exec-tkcard { border:1px solid var(--line); border-radius:8px; background:#fff; overflow:hidden; }
.dsh-exec-tkcard .dsh-exec-tbwrap { border:none; border-radius:0; }
.dsh-exec-tkpg { display:flex; align-items:center; gap:8px; padding:9px 14px; border-top:1px solid #ebeef5; flex-wrap:wrap; }
.dsh-exec-tkpg .tpg-arr, .dsh-exec-tkpg .tpg-num { min-width:26px; height:24px; padding:0 9px; border:1px solid #dcdfe6;
  border-radius:4px; background:#fff; color:#606266; font-size:12px; line-height:22px; cursor:pointer; font-family:inherit; }
.dsh-exec-tkpg .tpg-arr:hover:not(:disabled), .dsh-exec-tkpg .tpg-num:hover { border-color:#409eff; color:#409eff; }
.dsh-exec-tkpg .tpg-arr:disabled { color:#c0c4cc; background:#f5f7fa; cursor:not-allowed; }
.dsh-exec-tkpg .tpg-num.act { background:#409eff; border-color:#409eff; color:#fff; }
.dsh-exec-tkpg .tpg-nums { display:inline-flex; gap:4px; align-items:center; }
.dsh-exec-tkpg .tpg-gap { padding:0 2px; color:#c0c4cc; }
.dsh-exec-tkpg .tpg-cnt { margin-left:auto; font-size:12px; color:#909399; white-space:nowrap; font-variant-numeric:tabular-nums; }

/* 错误事件 / 阻断 */
.dsh-exec-errs { list-style:none; margin:0; padding:0; }
.dsh-exec-errs li { display:flex; gap:10px; align-items:baseline; padding:7px 0; font-size:12px; border-bottom:1px dashed var(--line); color:var(--body); }
.dsh-exec-errs li:last-child { border-bottom:none; }
.dsh-exec-errs li.empty { color:var(--faint); font-style:italic; justify-content:center; padding:10px 0; }
.dsh-exec-errs li .src { flex:none; border-radius:4px; padding:0 6px; font-size:10.5px; color:#fff; }
.dsh-exec-errs .src.v2 { background:#e6a23c; } .dsh-exec-errs .src.os { background:#409eff; } .dsh-exec-errs .src.dsh { background:#909399; }
.dsh-exec-errs li time { flex:none; color:var(--faint); font-size:11px; font-variant-numeric:tabular-nums; }
.dsh-exec-errs li .line { flex:1 1 auto; color:var(--dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
/* 状态机徽标（error_events 去重事件） */
.dsh-exec-errs li .evst { flex:none; border-radius:3px; padding:0 5px; font-size:10px; line-height:1.7; font-weight:600; }
.dsh-exec-errs li .evst.st-open { background:#fef0f0; color:#f56c6c; border:1px solid #fbc4c4; }
.dsh-exec-errs li .evst.st-processing { background:#ecf5ff; color:#409eff; border:1px solid #b3d8ff; }
.dsh-exec-errs li .evst.st-resolved { background:#f0f9eb; color:#67c23a; border:1px solid #c2e7b0; }
.dsh-exec-errs li .evst.st-ignored { background:#f4f4f5; color:#909399; border:1px solid #d3d4d6; }
/* 事件 ID 徽标：短 ID 可复制（2026-09-10，用户反馈列表缺 ID 无法指认具体事件） */
.dsh-exec-errs li .evid { flex:none; border:1px solid #dcdfe6; background:#fafafa; color:#909399; border-radius:3px;
  padding:0 5px; font-size:10.5px; line-height:1.7; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; cursor:pointer; }
.dsh-exec-errs li .evid:hover { color:#409eff; border-color:#c6e2ff; background:#ecf5ff; }
.dsh-exec-errs li .evid.none { cursor:default; color:#c0c4cc; }
.dsh-exec-errs li .occ { flex:none; color:#f56c6c; font-size:10.5px; font-weight:700; font-variant-numeric:tabular-nums; }
.dsh-exec-errs li .asg { flex:none; color:#9254de; font-size:10.5px; background:#f5f0ff; border-radius:3px; padding:0 5px; white-space:nowrap; }
.dsh-exec-errs li .note { flex:none; color:#3f7f3f; font-size:10.5px; background:#f0f9eb; border-radius:3px; padding:0 5px; white-space:nowrap; max-width:260px; overflow:hidden; text-overflow:ellipsis; cursor:help; }
.dsh-exec-errs li .op { margin-left:auto; display:inline-flex; gap:6px; align-items:center; flex:none; }
.dsh-exec-errs li .op .dsh-exec-solve { margin-left:0; }
.dsh-exec-evact { flex:none; border:1px solid #dcdfe6; background:#fff; color:#606266; border-radius:5px; padding:1px 8px; font-size:11px; line-height:1.6; cursor:pointer; white-space:nowrap; vertical-align:middle; }
.dsh-exec-evact:hover { color:#409eff; border-color:#c6e2ff; background:#ecf5ff; }
.dsh-exec-block { display:flex; align-items:center; gap:10px; padding:8px 0; font-size:12.5px; }
.dsh-exec-block b { color:var(--text); font-weight:500; }
.dsh-exec-block .blocks { color:var(--faint); font-size:11.5px; }

/* ================= 我来解决（solve 投递） ================= */
/* 按钮：失败任务行「处理」列 + 错误事件条 */
.dsh-exec-solve {
  flex:none; border:1px solid #c6e2ff; background:#ecf5ff; color:#409eff;
  border-radius:5px; padding:2px 9px; font-size:11.5px; line-height:1.7;
  cursor:pointer; white-space:nowrap; vertical-align:middle;
}
.dsh-exec-solve:hover { background:#d9ecff; border-color:#79bbff; }
.dsh-exec-solve:active { background:#c6e2ff; }
.dsh-exec-tb td.op { text-align:center; white-space:nowrap; }
.dsh-exec-errs li .dsh-exec-solve { align-self:center; margin-left:auto; }
/* 选择器浮层：锚点下弹出的窗口列表 */
.dsh-exec-solvepop {
  position:fixed; z-index:9999; min-width:232px; max-width:300px;
  background:var(--panel,#fff); border:1px solid var(--border,#e4e7ed);
  border-radius:8px; box-shadow:0 6px 22px rgba(0,0,0,.16);
  padding:6px; font-size:12.5px; color:var(--body,#606266);
}
.dsh-exec-solvepop-head {
  padding:4px 8px 7px; color:var(--text,#303133); font-weight:600; font-size:12px;
  border-bottom:1px solid var(--line,#ebeef5); margin-bottom:4px;
}
.dsh-exec-solvepop-list { display:flex; flex-direction:column; max-height:264px; overflow-y:auto; }
.dsh-exec-solvepop-item {
  border:none; background:transparent; text-align:left; padding:5px 8px;
  border-radius:5px; cursor:pointer; color:var(--body,#606266); font:inherit; font-size:12.5px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.dsh-exec-solvepop-item:hover { background:var(--hover,rgba(128,128,128,.12)); }
.dsh-exec-solvepop-item.cur { color:#409eff; font-weight:600; }
.dsh-exec-solvepop-cancel {
  width:100%; margin-top:4px; border:none; background:transparent; color:var(--dim,#909399);
  font:inherit; font-size:12px; padding:4px; cursor:pointer; border-top:1px solid var(--line,#ebeef5);
}
.dsh-exec-solvepop-cancel:hover { color:var(--text,#303133); }
/* toast：投递结果飘字 */
.dsh-exec-toast {
  position:fixed; left:50%; bottom:54px; transform:translateX(-50%);
  z-index:10000; max-width:70vw; background:#303133; color:#fff;
  border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6;
  box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s;
}
.dsh-exec-toast.ok { background:#529b2e; }
.dsh-exec-toast.err { background:#e64545; }
.dsh-exec-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }

/* Orphaned tasks (僵尸任务) */
.dsh-exec-orphaned-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dsh-exec-orphaned-item {
  padding: 12px;
  border: 1px solid #ff6b6b33;
  border-radius: 6px;
  background: #ff6b6b11;
}

.dsh-exec-orphaned-item .orphaned-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dsh-exec-orphaned-item .task-name {
  font-weight: 500;
  color: #ff6b6b;
}

.dsh-exec-orphaned-item .tag {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
}

.dsh-exec-orphaned-item .tag.enabled {
  background: #ffc10733;
  color: #ffc107;
}

.dsh-exec-orphaned-item .tag.disabled {
  background: #9e9e9e33;
  color: #9e9e9e;
}

.dsh-exec-orphaned-item .orphaned-info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}

.dsh-exec-orphaned-item .orphaned-info .reason {
  flex: 1 1 100%;
  color: #ff6b6b;
}

.dsh-exec-orphaned-item .orphaned-actions {
  display: flex;
  justify-content: flex-end;
}

.dsh-exec-cleanup-btn {
  padding: 4px 12px;
  border: 1px solid #ff6b6b;
  border-radius: 4px;
  background: white;
  color: #ff6b6b;
  cursor: pointer;
  font-size: 13px;
}

.dsh-exec-cleanup-btn:hover {
  background: #ff6b6b;
  color: white;
}


.dsh-exec-orphaned-empty {
  padding: 24px;
  text-align: center;
  color: #28a745;
  font-size: 14px;
  background: #28a74511;
  border-radius: 6px;
}
`

/** Inject the stylesheet once (tagged for the HMR driver cleanup). */
export function injectStyles(): void {
  const id = "dsh-exec-styles"
  if (document.getElementById(id) !== null) return
  const style = document.createElement('style')
  style.id = id
  style.textContent = STYLES
  ;(document.head ?? document.documentElement).appendChild(style)
}