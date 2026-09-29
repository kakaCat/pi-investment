/**
 * pmboard 样式分片 · dag（REQ-260928001915-f978 真 DAG 画布面板；
 * REQ-260929010300-dbf9 FR-6 皮肤统一为会话面板的 np 苹果风）。
 *
 * 只负责**面板骨架**（工具条 / 画布滚动区 / 图例）——
 * 2026-09-29 用户裁定 B：标题行与统计条一并删除（需求详情与会话面板两处从简）。
 * 卡片、边线、进度条、绿点全部画在 canvas 内（见 client/dag/card-renderer.ts），
 * 不需要任何 DOM 样式。
 *
 * 皮肤口径（FR-6）：取值一律走 --dsh-pm-np-* 苹果风令牌（:root 定义在 styles/node-panel.ts），
 * 980px 胶囊 / 12px 圆角 / 轻描边——与需求详情、会话面板两处同源。
 * 底色裁定（2026-09-29 用户，见 REQ-260929010300-dbf9 卡验收）：面板与表头一律用
 * 泳道图底色 --dsh-pm-np-bg（#f5f5f7），**不是白底**——勿按「白底圆角」的字面描述改回白色。
 * 已知取舍：np 皮肤是固定浅色，本面板不再随明暗主题变化（用户 2026-09-29 追认）。
 *
 * 作用域纪律：每条规则的选择器都含 .dsh-pm-dag-*，与看板其它页面零冲突。
 * 命名注意：base.ts 里的 .dsh-pm-dag / -layer / -node 是**旧分层列表**的类，
 * 已被本面板取代；本片用 -panel / -head / -seg / -canvas-wrap / -legend，
 * 与旧类不重名（class 选择器按 token 精确匹配，-panel 不会被 .dsh-pm-dag 命中）。
 */
export const DAG_CSS = `
/* ---- 真 DAG 面板（demo ⑤ 的看板版；皮肤 = 会话面板 np 苹果风） ---- */
/* 底色 = 泳道图底色（--dsh-pm-np-bg / #f5f5f7，与 [泳道] 页签的列底一致）。 */
.dsh-pm-dag-panel {
  border: 1px solid var(--dsh-pm-np-line-soft);
  border-radius: 12px; overflow: hidden;
  background: var(--dsh-pm-np-bg);
}
.dsh-pm-dag-head {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 11px 13px 9px;
  border-bottom: 1px solid var(--dsh-pm-np-line-soft);
  background: var(--dsh-pm-np-bg);
}
.dsh-pm-dag-sub { font-size: 11.5px; color: var(--dsh-pm-np-text3); }
.dsh-pm-dag-seg { display: flex; gap: 4px; margin-left: auto; }
.dsh-pm-dag-seg + .dsh-pm-dag-seg { margin-left: 0; }
.dsh-pm-dag-btn {
  font: inherit; font-size: 11.5px; line-height: 1; padding: 4px 10px;
  border-radius: 980px; cursor: pointer;
  border: 1px solid var(--dsh-pm-np-line);
  background: #fff;
  color: var(--dsh-pm-np-text2);
}
.dsh-pm-dag-btn:hover { border-color: var(--dsh-pm-np-blue); color: var(--dsh-pm-np-blue); }
.dsh-pm-dag-btn.is-on { background: var(--dsh-pm-np-blue); border-color: var(--dsh-pm-np-blue); color: #fff; }

/* ---- 画布滚动区（高度上限内滚动；宽度自适应由 canvas 自己按容器重排） ---- */
.dsh-pm-dag-canvas-wrap { padding: 0 13px 6px; overflow: auto; max-height: 640px; }
.dsh-pm-dag-canvas-wrap::-webkit-scrollbar { width: 8px; height: 8px; }
.dsh-pm-dag-canvas-wrap::-webkit-scrollbar-track { background: var(--dsh-pm-np-bg); border-radius: 4px; }
.dsh-pm-dag-canvas-wrap::-webkit-scrollbar-thumb { background: var(--dsh-pm-np-line); border-radius: 4px; }
.dsh-pm-dag-canvas-wrap::-webkit-scrollbar-thumb:hover { background: var(--dsh-pm-np-text3); }
.dsh-pm-dag-canvas { display: block; }

/* ---- 图例 ---- */
.dsh-pm-dag-legend {
  display: flex; gap: 14px; flex-wrap: wrap; font-size: 11.5px;
  color: var(--dsh-pm-np-text2); padding: 7px 13px 12px;
}
.dsh-pm-dag-legend i {
  display: inline-block; width: 16px; height: 3px; border-radius: 2px;
  vertical-align: middle; margin-right: 5px;
}
`;
