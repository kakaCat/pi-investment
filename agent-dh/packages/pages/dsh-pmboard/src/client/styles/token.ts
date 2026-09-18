/**
 * Token tab 样式（REQ-a33899 t6）——只复用全站令牌（--dsw-* / --pm-*）与既有 .dsh-pm-* 体系，
 * 不造第二套色板；尺寸变体随本文件。
 */
export const TOKEN_CSS = `
/* ── 🪙 Token tab（REQ-a33899） ───────────────────────────────────────── */
.dsh-pm-tab-content[data-tab-content="token"] { display: flex; flex-direction: column; gap: 10px; }
.dsh-pm-callout {
  background: rgba(240, 195, 109, .16); border: 1px solid rgba(240, 195, 109, .5);
  border-radius: 8px; padding: 8px 12px; font-size: 12px; color: var(--dsw-text-primary, #5c4a12);
}
.dsh-pm-note { font-size: 12px; color: var(--dsw-text-secondary, #888); margin-top: 6px; }
.dsh-pm-sum { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: var(--dsw-text-secondary, #888); margin-bottom: 8px; }
.dsh-pm-sum b { color: var(--dsw-text-primary, #222); font-variant-numeric: tabular-nums; }
.dsh-pm-tok-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.dsh-pm-tok-table th { text-align: right; font-weight: 600; color: var(--dsw-text-secondary, #888); font-size: 12px;
  padding: 6px 8px; border-bottom: 1px solid var(--pm-line, #e5e7eb); }
.dsh-pm-tok-table th:first-child, .dsh-pm-tok-table td:first-child { text-align: left; }
.dsh-pm-tok-table td { padding: 7px 8px; border-bottom: 1px solid var(--pm-line, #e5e7eb); text-align: right; font-variant-numeric: tabular-nums; }
.dsh-pm-tok-node { cursor: pointer; }
.dsh-pm-tok-node:hover { background: var(--dsw-hover, rgba(128,128,128,.08)); }
.dsh-pm-tok-more { font-size: 11px; color: var(--dsw-text-secondary, #999); }
.dsh-pm-tok-sub { background: color-mix(in srgb, var(--pm-bg-soft, #f3f4f6) 55%, transparent); }
.dsh-pm-tok-sub td { font-size: 12px; color: var(--dsw-text-secondary, #888); padding: 5px 8px 5px 26px; text-align: left; }
.dsh-pm-tok-sub-num { float: right; color: var(--dsw-text-primary, #333); font-variant-numeric: tabular-nums; }
.dsh-pm-nosnap { color: var(--dsw-text-secondary, #b0b4bb); }
.dsh-pm-bar { display: inline-block; width: 72px; height: 6px; border-radius: 3px; background: var(--pm-line, #e5e7eb); vertical-align: middle; }
.dsh-pm-bar > i { display: block; height: 6px; border-radius: 3px; background: #4a7dff; }
.dsh-pm-impact-row { display: flex; align-items: center; gap: 10px; font-size: 12px; margin: 5px 0; }
.dsh-pm-impact-name { width: 150px; color: var(--dsw-text-secondary, #888); }
.dsh-pm-impact-bar { flex: 1; height: 8px; border-radius: 4px; background: var(--pm-bg-soft, #f3f4f6); overflow: hidden; }
.dsh-pm-impact-bar > i { display: block; height: 8px; background: rgba(194, 37, 92, .75); }
.dsh-pm-impact-val { width: 90px; text-align: right; font-variant-numeric: tabular-nums; }
details.dsh-pm-prompt { border: 1px solid var(--pm-line, #e5e7eb); border-radius: 6px; margin: 6px 0; background: var(--pm-bg-soft, #fbfbfc); }
details.dsh-pm-prompt > summary { list-style: none; cursor: pointer; padding: 7px 10px; font-size: 12px;
  display: flex; align-items: center; gap: 8px; }
details.dsh-pm-prompt > summary::-webkit-details-marker { display: none; }
details.dsh-pm-prompt > summary::before { content: '\\25B8'; color: var(--dsw-text-secondary, #999); font-size: 10px; }
details.dsh-pm-prompt[open] > summary::before { transform: rotate(90deg); }
details.dsh-pm-prompt > summary:hover { background: var(--dsw-hover, rgba(128,128,128,.08)); }
.dsh-pm-prompt-name { font-weight: 600; color: var(--dsw-text-primary, #333); }
.dsh-pm-prompt-meta { margin-left: auto; color: var(--dsw-text-secondary, #999); font-variant-numeric: tabular-nums; }
.dsh-pm-prompt-text { margin: 0; padding: 10px 12px; border-top: 1px dashed var(--pm-line, #e5e7eb);
  background: var(--dsw-bg-primary, #fff); font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px; line-height: 1.55; color: var(--dsw-text-primary, #3b4048);
  white-space: pre-wrap; word-break: break-word; max-height: 220px; overflow: auto; }
/* 会话顶部流程图：token 与节点名同一行（既有 .dsh-pm-flow-node 列布局不变） */
.dsh-pm-flow-meta { display: flex; align-items: baseline; gap: 4px; white-space: nowrap; }
.dsh-pm-flow-token { font-size: 10px; color: var(--dsw-text-primary, #333); font-variant-numeric: tabular-nums; }
/* 卡面 / 列表：累计 token 徽章 */
.dsh-pm-token-badge { display: inline-flex; align-items: center; gap: 3px; margin-left: 6px; font-size: 10px;
  padding: 1px 6px; border-radius: 9px; background: rgba(194, 37, 92, .10); color: #c2255c; font-variant-numeric: tabular-nums; }
`
