/**
 * 「🏷 条款接收状态」块样式（REQ-d3e61a T-5）——复用全站令牌（--dsw-*），不造第二套色板。
 * unreceived 用左侧红条 + 红字，**同时**着色整行，保证色弱/打印场景下也能看出异常。
 */
export const MARKS_CSS = `
/* ── 🏷 条款接收状态（REQ-d3e61a T-5） ─────────────────────────────────── */
.dsh-pm-mk-sum { font-size: 12px; color: var(--dsw-text-secondary, #888); margin-bottom: 8px; }
.dsh-pm-mk-sum.dsh-pm-mk-alert {
  color: #b42318; font-weight: 600; background: rgba(217, 45, 32, .08);
  border-left: 3px solid #d92d20; border-radius: 4px; padding: 6px 10px;
}
.dsh-pm-mk-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.dsh-pm-mk-table th {
  text-align: left; font-weight: 600; color: var(--dsw-text-secondary, #888);
  font-size: 12px; padding: 6px 8px; border-bottom: 1px solid var(--pm-line, #e5e7eb);
}
.dsh-pm-mk-table td { padding: 7px 8px; border-bottom: 1px solid var(--pm-line, #e5e7eb); }
.dsh-pm-mk-row.is-unreceived { background: rgba(217, 45, 32, .06); box-shadow: inset 3px 0 0 #d92d20; }
.dsh-pm-mk-id { font-variant-numeric: tabular-nums; font-weight: 600; }
.dsh-pm-mk-unreceived { color: #b42318; font-weight: 700; }
.dsh-pm-mk-done { color: #027a48; }
.dsh-pm-mk-received { color: var(--dsw-text-primary, #222); }
.dsh-pm-mk-skipped { color: var(--dsw-text-secondary, #999); }
.dsh-pm-mk-by { font-size: 12px; color: var(--dsw-text-secondary, #888); font-variant-numeric: tabular-nums; }
`;
