/**
 * Genome dashboard styles — scoped under .dsh-gen-* (own namespace).
 * Injected once into <head>; re-apply guarded by CSS_TAG id.
 * Tokens: ride the shell's --dsw-* CSS variables where exposed, with neutral
 * fallbacks. Board visibility: hidden unless html[data-dsh-gen-active].
 *
 * @module dashboard-genome/client/styles
 */

const CSS_TAG = '@pi-investment/dashboard-genome/styles'

export function injectStyles(): void {
  if (document.getElementById(CSS_TAG) !== null) return
  const style = document.createElement('style')
  style.id = CSS_TAG
  style.textContent = `
/* ===== 板容器与显隐（dsh-taskboard 契约） ===== */
.dsh-gen-board {
  display: none;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
  padding: 16px 20px 40px;
  overflow-y: auto;
  font-family: var(--dsw-font, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif);
  color: var(--dsw-text-1, #1f2329);
  background: transparent;
}
html[data-dsh-gen-active] .dsh-gen-board { display: flex; }
/* 三代中心列特征各配隐藏兜底（bulletin 同款：data-pane dev shell / centerCol 官方布局 / Desktop surface） */
html[data-dsh-gen-active] [data-pane="conversation"] > *:not([data-dsh-gen-view]),
html[data-dsh-gen-active] [class*="centerCol"] > *:not([data-dsh-gen-view]),
html[data-dsh-gen-active] .dshDesktopConversationSurface > *:not([data-dsh-gen-view]) { display: none !important; }
html[data-dsh-gen-active] .dsh-gen-board code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  background: var(--dsw-bg-2, rgba(0,0,0,0.05));
  padding: 1px 5px;
  border-radius: 4px;
}

/* ===== 头部行 ===== */
.dsh-gen-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.dsh-gen-meta {
  flex: 1;
  font-size: 11px;
  color: var(--dsw-text-3, #8a8f99);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dsh-gen-recheck {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--dsw-border, #dcdfe6);
  border-radius: 6px;
  background: var(--dsw-bg-1, #fff);
  color: var(--dsw-text-2, #4e5969);
  font-size: 12px;
  padding: 4px 10px;
  cursor: pointer;
  white-space: nowrap;
}
.dsh-gen-recheck:hover { border-color: var(--dsw-primary, #2f6bff); color: var(--dsw-primary, #2f6bff); }
.dsh-gen-close {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--dsw-border, #dcdfe6);
  border-radius: 6px;
  background: var(--dsw-bg-1, #fff);
  color: var(--dsw-text-2, #4e5969);
  font-size: 12px;
  padding: 4px 10px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}
.dsh-gen-close:hover { border-color: #f53f3f; color: #f53f3f; }

/* ===== 徽章 ===== */
.dsh-gen-badge {
  display: inline-block;
  font-size: 11px;
  line-height: 1;
  padding: 3px 7px;
  border-radius: 10px;
  white-space: nowrap;
}
.dsh-gen-badge.ok   { background: #e1f5e8; color: #0a7d33; }
.dsh-gen-badge.bad  { background: #fde2e2; color: #c41d1d; }
.dsh-gen-badge.wait { background: #e8f0fe; color: #1d5fd6; }
.dsh-gen-badge.due  { background: #fff3d6; color: #ad6b00; }
.dsh-gen-badge.ev   { background: #e9f7fa; color: #0e7c8c; }
.dsh-gen-badge.lock { background: #efe9f7; color: #6b3fa0; }
.dsh-gen-badge.up   { background: #e8f0fe; color: #1d5fd6; }
.dsh-gen-badge.unk  { background: #f0f1f3; color: #6b7280; }

/* ===== ① 概览 ===== */
.dsh-gen-ov {
  border: 1px solid var(--dsw-border, #dcdfe6);
  border-radius: 10px;
  background: var(--dsw-bg-1, #fff);
  padding: 14px 16px;
  margin-bottom: 14px;
}
.dsh-gen-ov-title { display: flex; flex-direction: column; gap: 2px; margin-bottom: 10px; }
.dsh-gen-ov-big { font-size: 17px; font-weight: 700; }
.dsh-gen-ov-sub { font-size: 11px; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-ov-stats { display: flex; flex-wrap: wrap; gap: 22px; }
.dsh-gen-stat { display: flex; flex-direction: column; gap: 2px; }
.dsh-gen-stat-k { font-size: 10px; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-stat-v { font-size: 16px; font-weight: 700; }
.dsh-gen-stat-v small { font-size: 11px; font-weight: 400; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-gv { color: var(--dsw-primary, #2f6bff); }
.dsh-gen-warn-txt { color: #c41d1d; }
.dsh-gen-ov-meta { margin-top: 8px; font-size: 11px; color: var(--dsw-text-3, #8a8f99); }

/* ===== 通用块 ===== */
.dsh-gen-block {
  border: 1px solid var(--dsw-border, #dcdfe6);
  border-radius: 10px;
  background: var(--dsw-bg-1, #fff);
  padding: 12px 14px;
  margin-bottom: 14px;
}
.dsh-gen-block-h { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }
.dsh-gen-block-t { font-size: 13px; font-weight: 700; }
.dsh-gen-block-s { font-size: 11px; color: var(--dsw-text-3, #8a8f99); }

/* ===== 展开（details） ===== */
.dsh-gen-exp summary {
  cursor: pointer;
  font-size: 11px;
  color: var(--dsw-text-3, #8a8f99);
  user-select: none;
}
.dsh-gen-exp summary:hover { color: var(--dsw-primary, #2f6bff); }
.dsh-gen-exp-body {
  font-size: 11px;
  line-height: 1.6;
  color: var(--dsw-text-2, #4e5969);
  background: var(--dsw-bg-2, rgba(0,0,0,0.03));
  border-radius: 6px;
  padding: 6px 8px;
  margin-top: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ===== ② 段矩阵（纵向全宽：全文阅读优先） ===== */
.dsh-gen-sec-grid { display: flex; flex-direction: column; gap: 10px; }
.dsh-gen-sec-card {
  border: 1px solid var(--dsw-border, #e5e6eb);
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--dsw-bg-1, #fff);
}
.dsh-gen-sec-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dsh-gen-sec-head .dsh-gen-badge { margin-left: auto; }
.dsh-gen-sec-name { font-size: 13px; font-weight: 600; }
.dsh-gen-sec-ver {
  font-size: 12px;
  font-weight: 600;
  color: var(--dsw-primary, #2f6bff);
  background: var(--dsw-bg-2, rgba(47,107,255,0.08));
  border-radius: 4px;
  padding: 1px 6px;
}
.dsh-gen-sec-body summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: var(--dsw-primary, #2f6bff);
  padding: 2px 0;
  user-select: none;
}
.dsh-gen-sec-body summary:hover { text-decoration: underline; }
.dsh-gen-sec-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.75;
  color: var(--dsw-text-1, #1f2329);
  background: var(--dsw-bg-2, rgba(0,0,0,0.025));
  border: 1px solid var(--dsw-border, #eef0f3);
  border-radius: 6px;
  padding: 10px 12px;
  margin: 4px 0 2px;
  max-height: 360px;
  overflow-y: auto;
}
.dsh-gen-sec-empty { font-size: 11px; color: var(--dsw-text-4, #c9cdd4); }
.dsh-gen-lc-head { font-size: 11px; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-lc-empty { font-size: 11px; color: var(--dsw-text-4, #c9cdd4); }

/* ===== ③ 一致性 ===== */
.dsh-gen-cons-head {
  font-size: 12px;
  font-weight: 600;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.dsh-gen-cons-head.ok  { background: #e1f5e8; color: #0a7d33; }
.dsh-gen-cons-head.bad { background: #fde2e2; color: #c41d1d; }
.dsh-gen-iss-list { display: flex; flex-direction: column; gap: 6px; }
.dsh-gen-iss {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  border-radius: 6px;
  padding: 6px 10px;
  background: var(--dsw-bg-2, rgba(0,0,0,0.03));
}
.dsh-gen-iss.ok { background: #f3fbf5; }
.dsh-gen-iss.bad { background: #fdf4f4; }
.dsh-gen-iss-id { font-weight: 700; min-width: 26px; }
.dsh-gen-iss.ok .dsh-gen-iss-id { color: #0a7d33; }
.dsh-gen-iss.bad .dsh-gen-iss-id { color: #c41d1d; }
.dsh-gen-iss-t { flex: 1; }
.dsh-gen-iss-r { font-size: 11px; font-weight: 600; }
.dsh-gen-iss.ok .dsh-gen-iss-r { color: #0a7d33; }
.dsh-gen-iss.bad .dsh-gen-iss-r { color: #c41d1d; }
.dsh-gen-iss-desc { font-size: 11px; color: var(--dsw-text-3, #8a8f99); padding: 0 4px; }
.dsh-gen-iss-item {
  font-size: 11px;
  color: #c41d1d;
  border-left: 2px solid #e5b8b8;
  background: #fdf6f6;
  border-radius: 0 4px 4px 0;
  padding: 4px 8px;
  margin: 0 4px;
}
.dsh-gen-iss-reason { color: #8a5a5a; margin-top: 2px; word-break: break-all; }

/* ===== ④ 候选 ===== */
.dsh-gen-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.dsh-gen-tab {
  border: 1px solid var(--dsw-border, #dcdfe6);
  background: var(--dsw-bg-1, #fff);
  color: var(--dsw-text-2, #4e5969);
  border-radius: 12px;
  font-size: 11px;
  padding: 3px 10px;
  cursor: pointer;
}
.dsh-gen-tab.on { background: var(--dsw-primary, #2f6bff); border-color: var(--dsw-primary, #2f6bff); color: #fff; }
.dsh-gen-cand-list { display: flex; flex-direction: column; gap: 8px; }
.dsh-gen-cand-empty { font-size: 12px; color: var(--dsw-text-4, #c9cdd4); padding: 14px 0; text-align: center; }
.dsh-gen-cand {
  border: 1px solid var(--dsw-border, #e5e6eb);
  border-radius: 8px;
  padding: 8px 12px;
  background: var(--dsw-bg-1, #fff);
}
.dsh-gen-cand-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dsh-gen-cand-sec { font-size: 12px; font-weight: 700; }
.dsh-gen-cand-gv { font-size: 11px; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-cand-id { margin-left: auto; font-size: 10px; color: var(--dsw-text-4, #c9cdd4); }
.dsh-gen-cand-mut { font-size: 10px; color: #6b3fa0; border: 1px solid #d8c9ec; border-radius: 8px; padding: 1px 6px; }
.dsh-gen-cand-bar { height: 5px; border-radius: 3px; background: var(--dsw-bg-2, #e5e6eb); margin-top: 8px; overflow: hidden; }
.dsh-gen-cand-bar-in { height: 100%; background: linear-gradient(90deg, #2f6bff, #53a0ff); border-radius: 3px; }
.dsh-gen-cand-bar-meta { font-size: 10px; color: var(--dsw-text-3, #8a8f99); margin-top: 3px; }
.dsh-gen-cand-hc { font-size: 11px; color: var(--dsw-text-2, #4e5969); margin-top: 6px; }
.dsh-gen-cand-hc-extra { color: #c41d1d; font-size: 10px; }
.dsh-gen-cand-note { font-size: 11px; color: var(--dsw-text-2, #4e5969); margin-top: 6px; word-break: break-all; }

/* ===== ⑤ 时间线 ===== */
.dsh-gen-tl-empty { font-size: 12px; color: var(--dsw-text-4, #c9cdd4); padding: 10px 0; }
.dsh-gen-tl { position: relative; padding-left: 18px; }
.dsh-gen-tl::before {
  content: "";
  position: absolute;
  left: 5px; top: 4px; bottom: 4px;
  width: 1px;
  background: var(--dsw-border, #e5e6eb);
}
.dsh-gen-tl-item { position: relative; padding-bottom: 12px; }
.dsh-gen-tl-dot {
  position: absolute;
  left: -18px; top: 4px;
  width: 9px; height: 9px;
  border-radius: 50%;
  background: #c9cdd4;
  border: 2px solid var(--dsw-bg-1, #fff);
}
.dsh-gen-tl-dot.ok  { background: #0a7d33; }
.dsh-gen-tl-dot.up  { background: #2f6bff; }
.dsh-gen-tl-dot.bad { background: #c41d1d; }
.dsh-gen-tl-main { display: flex; flex-direction: column; gap: 3px; }
.dsh-gen-tl-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dsh-gen-tl-gv { font-size: 12px; font-weight: 700; color: var(--dsw-primary, #2f6bff); }
.dsh-gen-tl-sec { font-size: 12px; font-weight: 600; }
.dsh-gen-tl-ts { font-size: 10px; color: var(--dsw-text-4, #c9cdd4); margin-left: auto; }

/* ===== 侧栏入口 ===== */
.dsh-gen-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  width: calc(100% - 16px);
  margin: 4px 8px;
  padding: 7px 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--dsw-text-2, #4e5969);
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  box-sizing: border-box;
}
.dsh-gen-entry:hover { background: var(--dsw-bg-2, rgba(0,0,0,0.06)); color: var(--dsw-primary, #2f6bff); }
html[data-dsh-gen-active] .dsh-gen-entry { background: var(--dsw-primary, #2f6bff); color: #fff; }
html[data-dsh-gen-active] [data-dsh-gen-entry] svg { stroke: #fff; }
.dsh-gen-entry svg { flex: none; stroke: var(--dsw-text-2, #4e5969); }
html[data-dsh-gen-active] [data-dsh-gen-entry] { background: color-mix(in srgb, var(--dsw-primary, #2f6bff) 14%, transparent); }
[data-sidebar-collapsed] .dsh-gen-entry,
[class*="_collapsed"] .dsh-gen-entry { justify-content: center; width: 36px; margin: 4px auto; padding: 7px 0; }
[data-sidebar-collapsed] .dsh-gen-entry .dsh-gen-entry-label,
[class*="_collapsed"] .dsh-gen-entry .dsh-gen-entry-label { display: none; }
`
  ;(document.head ?? document.documentElement).appendChild(style)
}
