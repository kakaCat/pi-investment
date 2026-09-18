# REQ-a33899 UI 设计（Token 消耗三处展示）· v3

- **可交互原型**：[token-ui.html](./token-ui.html)（v3；渲染图 token-ui.png）
- **v3 修订**（按用户意见）：① 会话顶部**沿用现有样式不变**（圆点在上、名称在下），只把 token 与名称**同一行水平**放在名称行；
  ② Token tab 内容**分块折叠**（沿用既有 details.dsh-pm-fold），不再平铺一堆表；
  ③ 固定系统提示词**可逐段展开查看具体提示词内容**（不只是数字）。
- **页面插件契约**：复用 .dsh-pm-* / .dsh-pm-flow-* 类与 var(--dsw-*) 令牌，不造第二套按钮或色板。

## 0 三处展示的信息层级

| 位置 | 回答的问题 | 密度 |
|------|-----------|------|
| 看板卡面 | 这个需求一共花了多少？ | 一个徽章数字 |
| 会话顶部进度条 | 每个阶段花了多少？我在哪一段？ | 名称行内一个 token 小字 |
| 详情页 Token tab | 花到哪去了？谁最费？固定系统提示词/注入提示词分别占多少、内容是什么？ | 汇总卡 + 四个折叠块 |

---

## 1 需求详情页新增「🪙 Token」tab（第 5 个 tab）

### 1.1 布局（常显汇总 + 四个折叠块）

    ┌────────────────────────────────────────────────────────────────┐
    │ [汇总卡·常显] 总Token│未缓存输入│输出│缓存读│费用估算(¥)          │
    ├────────────────────────────────────────────────────────────────┤
    │ ▸ 📊 按流程节点        7 个节点 · 合计 460.0k           [展开]  │
    │ ▸ 🧱 固定系统提示词     每回合 ≈14.2k · 回合 74 · 累计 1.05M     │
    │ ▸ 💉 注入提示词         128 次 · 160.8k（估算）· 占 35.0%       │
    │ ▸ ℹ️ 口径说明                                                  │
    └────────────────────────────────────────────────────────────────┘

「按流程节点」展开后：节点表（Token/未缓存/输出/缓存读/费用/占比，行可点开下钻任务）；
「固定系统提示词」展开后：合计行 + **每段一个二级折叠**（summary=段名+字符+估算token+占比，body=该段**具体提示词内容**）；
「注入提示词」展开后：合计行 + 按阶段横条 + **每次注入一个二级折叠**（summary=时间/routeKey/字符/token，body=注入内容摘要与命中片段）。

### 1.2 DOM 结构

    <button type="button" class="dsh-pm-tab" data-action="switch-tab" data-tab="token">🪙 Token</button>

    <div class="dsh-pm-tab-content" data-tab-content="token">
      <div class="dsh-pm-stats"> … 五格汇总（常显）… </div>

      <details class="dsh-pm-fold" open>
        <summary>📊 按流程节点<span class="dsh-pm-fold-count">7 个节点 · 合计 460.0k</span></summary>
        <div class="dsh-pm-fold-body">
          <table class="dsh-pm-tok-table">
            <tr class="dsh-pm-tok-node" data-action="toggle-token-node" data-stage="implementing">…</tr>
            <tr class="dsh-pm-tok-sub">t1 …<span class="num">28.4k · ¥0.14</span></tr>
          </table>
        </div>
      </details>

      <details class="dsh-pm-fold">
        <summary>🧱 固定系统提示词<span class="dsh-pm-fold-count">每回合 ≈14.2k · 回合 74 · 累计 ≈1.05M</span></summary>
        <div class="dsh-pm-fold-body">
          <div class="dsh-pm-sum">… 本次装配合计 28,410 字符 · 74 回合 · 来源 systemPrompt.assemble …</div>
          <details class="dsh-pm-prompt">
            <summary><span class="pname">genome:rules（规则）</span><span class="pmeta">4,860 字符 · 2.4k · 17.1%</span></summary>
            <pre class="dsh-pm-prompt-text">R-001 买入前确认…… R-013 数据来源标注……</pre>   <!-- 具体提示词内容 -->
          </details>
        </div>
      </details>

      <details class="dsh-pm-fold">
        <summary>💉 注入提示词<span class="dsh-pm-fold-count">128 次 · 160.8k（估算）· 占 35.0%</span></summary>
        <div class="dsh-pm-fold-body">
          <div class="dsh-pm-impact-row"><span class="name">实施（implementing）</span>
            <span class="bar"><i style="width:52%"></i></span><span class="val">83.1k · 51.7%</span></div>
          <details class="dsh-pm-prompt">
            <summary><span class="pname">09-18 06:40 · implementing/heavy/feature</span>
              <span class="pmeta">3,620 字符 · 1.8k</span></summary>
            <pre class="dsh-pm-prompt-text"># 实施（implementing）· 重档 …… 命中片段：implementing.heavy, common.iron-rules</pre>
          </details>
        </div>
      </details>

      <details class="dsh-pm-fold">
        <summary>ℹ️ 口径说明</summary>
        <div class="dsh-pm-fold-body">…</div>
      </details>
    </div>

### 1.3 两块提示词成本的数据来源与「看内容」

| 块 | 数据源 | 口径 |
|----|--------|------|
| 🧱 固定系统提示词 | host 调 systemPrompt.assemble(scope) → sections[]/contexts[]/tools[]（每段 name + text） | 逐段字符 → 估算 token；每回合 = 本次装配合计；累计 = 每回合 × sessionStats.turns；**每段 text 直接渲染进折叠 body**（只读，不落台账） |
| 💉 注入提示词 | <dshHome>/state/prompt-injection-log.json（routeKey/fragmentIds/charCount/windowKey/at） | 只统计本需求会话窗口；按阶段聚合 + 逐条明细；字符 → 估算 token；明细 body 展示该次注入的片段与内容摘要 |

**降级**：systemPrompt 不可得 → 「固定系统提示词」块显示「不可用」并注明原因；注入留痕缺文件 → 「无注入记录」；均不阻断过程消耗主数据。

**内容量护栏**：提示词正文可能很长 → pre 设 max-height + 内部滚动（原型 220px），不撑破 tab。

### 1.4 类名清单

| 类名 | 用途 |
|------|------|
| details.dsh-pm-fold / .dsh-pm-fold-body / .dsh-pm-fold-count | 一级折叠块（复用既有） |
| details.dsh-pm-prompt / .pname / .pmeta / .dsh-pm-prompt-text | 二级折叠：每段/每次注入的**具体提示词内容** |
| .dsh-pm-tok-table / .dsh-pm-tok-node / .dsh-pm-tok-sub | 节点表与任务下钻 |
| .dsh-pm-bar / .dsh-pm-sum / .dsh-pm-impact-row | 占比条 / 合计行 / 阶段横条 |
| .dsh-pm-nosnap | 无快照占位（灰字，不显示 0） |

### 1.5 交互与状态

- 一级折叠默认：「按流程节点」open（首屏看主数据），其余折叠（避免一屏塞满）。
- 点节点行 → 该阶段任务明细显隐。
- 空态：无任何快照 → 汇总卡后显示 .dsh-pm-empty「该需求暂无 Token 快照」+ 口径说明。
- 降级态：口径说明块警示色，提示词块各自独立标注，不连坐。
- 费用缺失 → 「—」+ title「未取得模型单价」。

---

## 2 会话顶部流程进度条（现有样式不变，token 与名称同行）

### 2.1 形态

       ✓        ✓         ✓        ✓         ●        6        7
    立项 3.2k  需求分析 18.7k  技术设计 6.1k  拆分 2.4k  实施 428.5k  验收 —  归档 —

**圆点在上、名称在下（现有 .dsh-pm-flow-node 列布局完全不变）**；唯一新增 = 名称行内水平加一个 token 小字。

### 2.2 DOM（在既有 flow-node 内把 label 包进 meta 行）

    <div class="dsh-pm-flow-node" data-state="current" title="未缓存输入 72.6k · 输出 36.4k · 缓存读 319.5k · 费用估算 ¥2.11">
      <div class="dsh-pm-flow-dot">●</div>
      <div class="dsh-pm-flow-meta">
        <span class="dsh-pm-flow-label">实施</span>
        <span class="dsh-pm-flow-token">428.5k</span>
      </div>
    </div>
    <!-- 无快照：<span class="dsh-pm-flow-token none" title="无快照">—</span> -->

新增 CSS：.dsh-pm-flow-meta { display:flex; align-items:baseline; gap:4px; white-space:nowrap; }；
.dsh-pm-flow-token { font-size:10px; font-variant-numeric:tabular-nums; }。既有 .dsh-pm-flow-node/.dsh-pm-flow-dot/.dsh-pm-flow-label 样式不动。

### 2.3 规则

- 数据取 GET /session/:id/progress 每节点 tokens.total；复用既有 15s 轮询，不额外请求。
- 格式：1,234→1.2k；12,345→12.3k；1,234,567→1.2M；<1000 原数。
- 无 tokens → 「—」灰字（零噪音，不显示 0）。
- 悬停 title：四分桶 + 费用估算。
- 窄屏：.dsh-pm-flow 既有 overflow-x 自动横向滚动，不换行。

---

## 3 看板卡面 token 徽章

    <span class="dsh-pm-badge" title="未缓存输入 82.3k · 输出 41.2k · 缓存读 336.5k · 费用估算 ¥2.31">🪙 460.0k</span>

- 位置：卡面 meta 行（状态徽章右侧），列表视图同样在对应行。
- 无 tokenTotals → 不渲染徽章（零噪音）。

---

## 4 数字格式化（单点，host/client 共用）

    export function fmtTokens(n: number): string   // 1234→1.2k / 1234567→1.2M / <1000 原数
    export function fmtCny(n: number | undefined): string  // undefined→—；否则 ¥1.23

所有**估算值**（费用、字符折算 token）在 UI 上带「估算」字样或 title，不冒充 provider 上报（R-013）。

## 5 与既有页面的关系

- tab 顺序：概览 / 执行 / 时间线 / 归档 / **🪙 Token**（追加末位）。
- 折叠样式与概览 tab 的 details.dsh-pm-fold 完全一致（同一套 CSS）。
- 会话顶部组件无绑定需求时仍返回 null（零噪音哲学不变）。
- 所有用户文本走 esc()；事件用 data-action 委派。
