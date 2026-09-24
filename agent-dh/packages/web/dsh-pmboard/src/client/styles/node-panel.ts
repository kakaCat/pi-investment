/**
 * pmboard 样式分片 · node-panel（REQ-260923134706-e72f / t5，FR-7 FR-8）。
 * 会话流程节点详情面板的苹果风皮肤，设计基线 stage-modals-alpine.html。
 *
 * 作用域纪律（TC-11）：除 :root 变量定义外，每条规则的选择器都含 .dsh-pm-np
 * （面板内容根）或是 .dsh-pm-cprog-detail-panel（本面板唯一外壳，无其他页面使用）——
 * 看板其他页面零影响。变量一律 --dsh-pm-np-* 前缀，不污染全局。
 */
export const NODE_PANEL_CSS = `
/* ===== Apple 风设计令牌（本面板私有） ===== */
:root {
  --dsh-pm-np-text: #1d1d1f;
  --dsh-pm-np-text2: #6e6e73;
  --dsh-pm-np-text3: #86868b;
  --dsh-pm-np-line: rgba(0,0,0,.12);
  --dsh-pm-np-line-soft: rgba(0,0,0,.08);
  --dsh-pm-np-bg: #f5f5f7;
  --dsh-pm-np-bg-hover: #ebebf0;
  --dsh-pm-np-blue: #0071e3;
  --dsh-pm-np-green: #34c759;
  --dsh-pm-np-red: #dc3545;
  --dsh-pm-np-amber: #ff9500;
}

/* ===== 面板外壳：锚定下拉（唯一使用方 = 会话流程面板） ===== */
.dsh-pm-cprog-detail-panel {
  width: min(720px, calc(100vw - 130px));
  max-height: 68vh; overflow-y: auto;
  background: #fff; border: 1px solid var(--dsh-pm-np-line);
  border-radius: 10px; box-shadow: 0 8px 28px rgba(0,0,0,.18);
  padding: 12px 14px; color: var(--dsh-pm-np-text);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.dsh-pm-cprog-detail-panel .dsh-pm-np-close {
  position: absolute; top: 10px; right: 12px; z-index: 2;
  width: 26px; height: 26px; border-radius: 50%; border: none; cursor: pointer;
  background: var(--dsh-pm-np-bg); color: var(--dsh-pm-np-text2); font-size: 15px; line-height: 1;
}
.dsh-pm-cprog-detail-panel .dsh-pm-np-close:hover { background: var(--dsh-pm-np-bg-hover); color: var(--dsh-pm-np-text); }

/* ===== 面板根 ===== */
.dsh-pm-np { display: flex; flex-direction: column; gap: 10px; text-align: left; font-size: 13.5px; }
.dsh-pm-np[data-state="skipped"] { opacity: .8; }

/* REQ 胶囊 + 标题行 */
.dsh-pm-np-req { display: flex; align-items: center; gap: 8px; padding-right: 30px; }
.dsh-pm-np-req-pill {
  flex: none; background: rgba(0,113,227,.1); color: var(--dsh-pm-np-blue);
  border-radius: 980px; padding: 2px 9px; font-size: 11.5px; font-weight: 600; font-variant-numeric: tabular-nums;
}
.dsh-pm-np-req-title {
  font-size: 15px; font-weight: 600; letter-spacing: -.01em; color: var(--dsh-pm-np-text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* 状态胶囊 + 一句话 + 时间行 */
.dsh-pm-np-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.dsh-pm-np-head-state {
  flex: none; border-radius: 980px; padding: 2px 9px; font-size: 11.5px; font-weight: 600;
  background: var(--dsh-pm-np-bg); color: var(--dsh-pm-np-text2);
}
.dsh-pm-np-head-state[data-state="current"] { background: rgba(0,113,227,.12); color: var(--dsh-pm-np-blue); }
.dsh-pm-np-head-state[data-state="done"] { background: rgba(52,199,89,.14); color: #248a3d; }
.dsh-pm-np-head-title { font-size: 13px; color: var(--dsh-pm-np-text2); }
.dsh-pm-np-head-time { margin-left: auto; font-size: 12px; color: var(--dsh-pm-np-text3); }

/* ===== 折叠块（原生 <details>） ===== */
.dsh-pm-np-fold { border-radius: 12px; }
.dsh-pm-np-fold > summary {
  list-style: none; cursor: pointer; user-select: none;
  display: flex; align-items: center; gap: 8px;
  background: var(--dsh-pm-np-bg); border-radius: 12px; padding: 10px 12px;
  transition: background .2s;
}
.dsh-pm-np-fold > summary::-webkit-details-marker { display: none; }
.dsh-pm-np-fold > summary:hover { background: var(--dsh-pm-np-bg-hover); }
.dsh-pm-np-fold-icon { color: var(--dsh-pm-np-text3); font-size: 12px; transition: transform .2s; }
.dsh-pm-np-fold[open] > summary .dsh-pm-np-fold-icon { transform: rotate(90deg); }
.dsh-pm-np-fold-text { font-size: 14px; font-weight: 600; letter-spacing: -.01em; color: var(--dsh-pm-np-text); }
.dsh-pm-np-fold-body { padding: 12px 4px 2px; display: flex; flex-direction: column; gap: 10px; }

/* ===== 基础信息 ===== */
.dsh-pm-np-info { display: flex; align-items: baseline; gap: 10px; }
.dsh-pm-np-info-label { flex: 0 0 auto; min-width: 96px; font-size: 12.5px; color: var(--dsh-pm-np-text2); white-space: nowrap; }
.dsh-pm-np-info-value { flex: 1 1 auto; min-width: 0; font-size: 13.5px; color: var(--dsh-pm-np-text); }
.dsh-pm-np-info-value.is-desc { white-space: pre-wrap; line-height: 1.5; }
.dsh-pm-np-tag {
  display: inline-block; background: rgba(0,113,227,.1); color: var(--dsh-pm-np-blue);
  border-radius: 980px; padding: 2px 10px; font-size: 12px; font-weight: 500;
}
.dsh-pm-np-sec-label { font-size: 12.5px; font-weight: 600; color: var(--dsh-pm-np-text); }
.dsh-pm-np-empty { font-size: 12.5px; color: var(--dsh-pm-np-text3); padding: 6px 0; }

/* 文档列表（白底圆角 + 细分隔线） */
.dsh-pm-np-doclist { display: block; background: #fff; border: 1px solid var(--dsh-pm-np-line-soft); border-radius: 12px; overflow: hidden; }
.dsh-pm-np-docitem {
  display: flex; align-items: center; gap: 8px; width: 100%; text-align: left;
  padding: 10px 12px; border: none; border-bottom: 1px solid var(--dsh-pm-np-line-soft);
  background: #fff; cursor: pointer; font: inherit;
}
.dsh-pm-np-docitem:last-child { border-bottom: none; }
.dsh-pm-np-docitem:hover { background: #fafafa; }
.dsh-pm-np-docitem-icon { flex: none; font-size: 13px; }
.dsh-pm-np-docitem-name { flex: 1 1 auto; min-width: 0; font-size: 13px; color: var(--dsh-pm-np-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dsh-pm-np-docitem-arrow { flex: none; color: #c7c7cc; }

/* 设计文档逐份 ✅/⬜ */
.dsh-pm-np-designdoc { font-size: 12.5px; padding: 3px 0; color: var(--dsh-pm-np-text); }
.dsh-pm-np-designdoc[data-submitted="no"] { color: var(--dsh-pm-np-text3); }

/* ===== 实施双视图：tab + DAG + 泳道 ===== */
.dsh-pm-np-tabs { display: flex; gap: 6px; margin-top: 4px; }
.dsh-pm-np-tab {
  border: 1px solid var(--dsh-pm-np-line-soft); border-radius: 980px; background: #fff;
  padding: 5px 14px; font-size: 12.5px; font-weight: 500; color: var(--dsh-pm-np-text2); cursor: pointer;
}
.dsh-pm-np-tab.is-active { background: var(--dsh-pm-np-blue); border-color: var(--dsh-pm-np-blue); color: #fff; }
.dsh-pm-np-pane { margin-top: 8px; }
/* 2026-09-24 用户两轮裁定：泳道区横向滚动条 4px 太细不好抓 → 12px 又太粗 → 定 8px；
   轨道淡底、滑块加深并留 hover 反馈（拖拽有目标，但存在感不抢戏）。 */
.dsh-pm-np-pane[data-pane="list"] { overflow-x: auto; padding-bottom: 6px; }
.dsh-pm-np-pane[data-pane="list"]::-webkit-scrollbar { height: 8px; }
.dsh-pm-np-pane[data-pane="list"]::-webkit-scrollbar-track { background: rgba(0,0,0,.05); border-radius: 4px; }
.dsh-pm-np-pane[data-pane="list"]::-webkit-scrollbar-thumb { background: rgba(0,0,0,.26); border-radius: 4px; }
.dsh-pm-np-pane[data-pane="list"]::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,.42); }
.dsh-pm-np-pane-caption { font-size: 12px; color: var(--dsh-pm-np-text3); margin: 0 0 10px; }

/* DAG 分层 */
.dsh-pm-np-dag { display: flex; flex-direction: column; gap: 8px; }
.dsh-pm-np-dag-layer { display: flex; align-items: flex-start; gap: 10px; }
.dsh-pm-np-dag-label { flex: 0 0 auto; min-width: 120px; font-size: 11.5px; color: var(--dsh-pm-np-text3); padding-top: 5px; }
.dsh-pm-np-dag-row { display: flex; flex-wrap: wrap; gap: 6px; }
/* DAG 节点 = 与泳道卡片同构（苹果风白底小圆角阴影，用户裁定 2026-09-23）。
   2026-09-24 用户裁定（验收实测）：DAG 卡片与泳道卡片外观完全一致——几何对齐
   （gap 2px / padding 6px 8px / min-height 44px；宽 208px = 220px 列 - 列体 12px 内边距，
   与泳道卡片实渲染宽度一致）；状态色不再另设，直接共用下方泳道卡片的六状态规则。 */
.dsh-pm-np-dag-node {
  display: flex; flex-direction: column; gap: 2px; text-align: left; cursor: default; font: inherit;
  background: #fff; border: none; border-radius: 9px; padding: 6px 8px;
  flex: 0 0 208px; width: 208px; min-height: 44px; box-sizing: border-box;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
  overflow: hidden;
}
/* 内层编号/名称复用 .dsh-pm-np-card-id / .dsh-pm-np-card-title（与泳道卡片同一套样式，上下结构一致） */
.dsh-pm-np-dag-node[data-action="open-doc"] { cursor: pointer; }
.dsh-pm-np-dag-node[data-action="open-doc"]:hover { box-shadow: 0 3px 10px rgba(0,0,0,.13); }

/* 泳道 = 竖向 6 列看板（FR-7 用户裁定 2026-09-23）：6 条状态列等宽排开，列头状态名+数量胶囊，列内卡片竖排、超出列内纵向滚动。
   2026-09-24 用户裁定修订（实测反馈）：① 列灰底全高——去掉 align-items:start，grid 默认 stretch 让所有列（含空列）
   灰底拉到同一高度，容器 min-height 200px 兜底保证稀疏时也有看板感；② 放弃「无横向滚动」——列设保底宽，
   面板容不下时泳道区横向滚动（pane 已有 overflow-x:auto），不再把列压扁。
   2026-09-24 用户裁定再修订（验收实测）：列保底宽 150px → 220px——卡片标题文字更宽、尽量一行放下
   （内容宽 ≈ 220-28=192px，约 16 个汉字；超长标题仍走两行 clamp），横向滚动换取可读性。 */
.dsh-pm-np-cols { display: grid; grid-template-columns: repeat(6, minmax(220px, 1fr)); gap: 8px; min-height: 200px; }
.dsh-pm-np-col {
  display: flex; flex-direction: column; min-height: 0; max-height: 340px; height: 100%;
  background: var(--dsh-pm-np-bg); border-radius: 8px;
  overflow: hidden;
}
.dsh-pm-np-col-head {
  flex: none; padding: 8px 8px 6px;
  font-size: 11px; font-weight: 600; color: var(--dsh-pm-np-text2); letter-spacing: .01em;
  display: flex; align-items: center; gap: 5px; justify-content: flex-start; white-space: nowrap;
}
.dsh-pm-np-col-count {
  min-width: 16px; height: 16px; line-height: 16px; text-align: center;
  background: rgba(0,0,0,.06); color: var(--dsh-pm-np-text3); font-weight: 500;
  border-radius: 8px; font-size: 10.5px; padding: 0 4px;
  font-variant-numeric: tabular-nums;
}
/* 列头状态色提示（2026-09-24 用户裁定）：状态色点 + 同色计数胶囊——数量为 0 时也能一眼看出这条泳道是什么状态。
   色值取自泳道卡片的状态色（同一状态两处一色，不另起一套）。 */
.dsh-pm-np-col-head::before {
  content: ""; flex: none; width: 7px; height: 7px; border-radius: 50%;
  background: #c7c7cc; box-shadow: 0 0 0 3px rgba(199,199,204,.18);
}
.dsh-pm-np-col[data-col="in_progress"] .dsh-pm-np-col-head::before { background: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,.15); }
.dsh-pm-np-col[data-col="in_progress"] .dsh-pm-np-col-count { background: rgba(0,113,227,.12); color: #0071e3; }
.dsh-pm-np-col[data-col="integrating"] .dsh-pm-np-col-head::before { background: #8e44ad; box-shadow: 0 0 0 3px rgba(142,68,173,.15); }
.dsh-pm-np-col[data-col="integrating"] .dsh-pm-np-col-count { background: rgba(142,68,173,.12); color: #8e44ad; }
.dsh-pm-np-col[data-col="testing"] .dsh-pm-np-col-head::before { background: #ff9500; box-shadow: 0 0 0 3px rgba(255,149,0,.16); }
.dsh-pm-np-col[data-col="testing"] .dsh-pm-np-col-count { background: rgba(255,149,0,.14); color: #b26a00; }
.dsh-pm-np-col[data-col="in_review"] .dsh-pm-np-col-head::before { background: #e91e63; box-shadow: 0 0 0 3px rgba(233,30,99,.14); }
.dsh-pm-np-col[data-col="in_review"] .dsh-pm-np-col-count { background: rgba(233,30,99,.12); color: #e91e63; }
.dsh-pm-np-col[data-col="done"] .dsh-pm-np-col-head::before { background: #34c759; box-shadow: 0 0 0 3px rgba(52,199,89,.16); }
.dsh-pm-np-col[data-col="done"] .dsh-pm-np-col-count { background: rgba(52,199,89,.14); color: #1d8a3c; }
.dsh-pm-np-col-body {
  flex: 1 1 auto; min-height: 0;
  /* 2026-09-24 实测修复：grid auto 行会把卡片压到 min-height、标题溢出到下一卡（视觉重叠）；
     回到设计稿最早版的 flex 竖排——行高随内容，卡片平铺不重叠。 */
  display: flex; flex-direction: column; gap: 5px;
  overflow-y: auto; overflow-x: hidden; padding: 0 6px 8px;
}
.dsh-pm-np-col-body::-webkit-scrollbar { width: 4px; }
.dsh-pm-np-col-body::-webkit-scrollbar-thumb { background: rgba(0,0,0,.14); border-radius: 2px; }
.dsh-pm-np-col-body::-webkit-scrollbar-track { background: transparent; }
/* 泳道卡片 = 苹果风白底小圆角阴影（设计稿定稿：border none + 9px radius + 轻阴影），列内占满宽度。
   用户裁定 2026-09-23：文字全部展示（允许换行、去掉省略号）；2026-09-24 用户裁定（截图定稿）：卡片高度随内容（去掉 grid-auto-rows:1fr 的拉伸等高），列高随内容包裹，只保留 min-height 44px 兜底。
   2026-09-24 用户裁定再修订：全文换行实测难看——标题改两行 clamp（与 DAG 节点一致），卡片高度两档（1 行/2 行）整齐平铺。 */
.dsh-pm-np-card {
  display: flex; flex-direction: column; gap: 2px; text-align: left; cursor: pointer;
  background: #fff; border: none; border-radius: 9px; padding: 6px 8px; font: inherit;
  width: 100%; min-height: 44px; box-sizing: border-box; flex: none;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
  overflow: hidden;
}
.dsh-pm-np-card[data-action="open-doc"]:hover { box-shadow: 0 3px 10px rgba(0,0,0,.13); }
.dsh-pm-np-card-id {
  font-family: ui-monospace, monospace; font-size: 10px; line-height: 12px; color: #a3abb8;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; flex: none;
}
/* 无任务卡文档的编号旁标记（2026-09-24 用户裁定：替代旧标题「（无任务卡）」后缀）：灰色淡化文档图标 */
.dsh-pm-np-nodoc { filter: grayscale(1); opacity: .45; font-size: 10px; margin-left: 3px; }
.dsh-pm-np-card-title {
  font-size: 11.5px; font-weight: 500; line-height: 15px; color: #1f2733; letter-spacing: -.005em;
  flex: none; white-space: normal; word-break: break-word;
  /* 两行 clamp（与 DAG 节点一致；全文不换行=卡片又高又乱，用户裁定 2026-09-24） */
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
/* 卡片带对应状态颜色：淡底（苹果风，无左边条；用户裁定 2026-09-23）。
   2026-09-24 用户裁定：DAG 节点与泳道卡片共用同一套六状态色（原 DAG 只有 done 绿 / 其余一律蓝两档，与泳道不一致）。 */
.dsh-pm-np-card[data-status="todo"], .dsh-pm-np-dag-node[data-status="todo"] { background: #fafafa; }
.dsh-pm-np-card[data-status="in_progress"], .dsh-pm-np-dag-node[data-status="in_progress"] { background: rgba(0,113,227,.06); }
.dsh-pm-np-card[data-status="integrating"], .dsh-pm-np-dag-node[data-status="integrating"] { background: rgba(142,68,173,.07); }
.dsh-pm-np-card[data-status="testing"], .dsh-pm-np-dag-node[data-status="testing"] { background: rgba(255,149,0,.08); }
.dsh-pm-np-card[data-status="in_review"], .dsh-pm-np-dag-node[data-status="in_review"] { background: rgba(233,30,99,.06); }
.dsh-pm-np-card[data-status="done"], .dsh-pm-np-dag-node[data-status="done"] { background: rgba(52,199,89,.08); }

/* ===== 执行流程三段 ===== */
.dsh-pm-np-sec { display: flex; flex-direction: column; gap: 6px; }
.dsh-pm-np-sec-title { font-size: 12.5px; font-weight: 600; color: var(--dsh-pm-np-text); letter-spacing: .01em; }
.dsh-pm-np-policy {
  background: var(--dsh-pm-np-bg); border-radius: 8px; padding: 7px 11px;
  font-size: 12.5px; color: var(--dsh-pm-np-text2);
}
.dsh-pm-np-inj-tpl { font-size: 12px; color: var(--dsh-pm-np-text2); display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.dsh-pm-np-doc {
  border: none; background: transparent; padding: 0; cursor: pointer; font: inherit;
  color: var(--dsh-pm-np-blue); font-size: 12px; text-decoration: none;
}
.dsh-pm-np-doc:hover { text-decoration: underline; }
.dsh-pm-np-shell { font-size: 12px; color: var(--dsh-pm-np-text3); }
.dsh-pm-np-inj-entry { display: flex; flex-direction: column; gap: 5px; }
.dsh-pm-np-inj-meta { font-size: 11.5px; color: var(--dsh-pm-np-text3); }
.dsh-pm-np-inj-meta code { font-family: ui-monospace, monospace; background: var(--dsh-pm-np-bg); border-radius: 4px; padding: 1px 5px; }
.dsh-pm-np-inj-frags { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }

/* 执行动作对照行 */
.dsh-pm-np-act { display: flex; align-items: baseline; gap: 8px; }
.dsh-pm-np-act-mark { flex: none; font-size: 12px; }
.dsh-pm-np-act-label { flex: 1 1 auto; min-width: 0; font-size: 12.5px; color: var(--dsh-pm-np-text); }
.dsh-pm-np-act-ev { flex: none; font-size: 11.5px; color: var(--dsh-pm-np-text3); }
.dsh-pm-np-act[data-done="yes"] .dsh-pm-np-act-label { color: var(--dsh-pm-np-text2); }

/* 隔离留痕 */
.dsh-pm-np-iso {
  display: flex; flex-direction: column; gap: 4px; background: var(--dsh-pm-np-bg);
  border-radius: 8px; padding: 8px 11px;
}
.dsh-pm-np-iso-status { font-size: 11px; font-weight: 600; color: var(--dsh-pm-np-blue); text-transform: uppercase; letter-spacing: .03em; }
.dsh-pm-np-iso[data-status="replaced"] .dsh-pm-np-iso-status { color: var(--dsh-pm-np-amber); }
.dsh-pm-np-iso[data-status="rejected"] .dsh-pm-np-iso-status { color: var(--dsh-pm-np-red); }
.dsh-pm-np-iso-meta { font-size: 11px; color: var(--dsh-pm-np-text3); }
.dsh-pm-np-iso-reason { font-size: 12px; color: var(--dsh-pm-np-text2); }

/* 验收单统计 */
.dsh-pm-np-stats { display: flex; flex-wrap: wrap; gap: 6px 14px; }
.dsh-pm-np-stat { font-size: 12.5px; color: var(--dsh-pm-np-text2); }
.dsh-pm-np-stat.is-pass { color: #248a3d; }
.dsh-pm-np-stat.is-fail { color: var(--dsh-pm-np-red); }
.dsh-pm-np-stat.is-pending { color: var(--dsh-pm-np-amber); }

/* 归档 */
.dsh-pm-np-archive-badge {
  display: inline-flex; align-items: center; gap: 6px; align-self: flex-start;
  background: rgba(52,199,89,.14); color: #248a3d; border-radius: 980px;
  padding: 4px 12px; font-size: 12.5px; font-weight: 600;
}
.dsh-pm-np-conclusion { font-size: 13px; color: var(--dsh-pm-np-text); line-height: 1.5; }
`;
