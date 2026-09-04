# RFC 013：公告板页面（dashboard-bulletin）

- 日期：2026-09-05
- 作者：investor（w-1cee2467）
- 状态：设计提案（待确认实施）
- 范围：agent-dh packages/pages 页面域新增第三个看板插件，镜像 dashboard-holdings / dashboard-execution 双半插件模式

## 1. 背景与目标

RFC 009 公告板引擎（board_post / board_read / board_update 工具，lifecycle 插件实现，存储于 Agent OS memory，tag office:board）已在生产运行，但只有“对话内工具”一种消费方式——没有 GUI。GUI 侧已有两块看板（账户持仓、双线执行确认），侧栏/中心栏/局部刷新的页面域模式成熟。

目标：新增 **公告板页面**，把帖子池（悬赏池/进行中/已完成）、认领状态、滞留告警以可视化面板呈现，供人工与多窗口 agent 监督协作。

## 2. 现状核实（2026-09-05 实测，非臆测）

数据源（Agent OS :8080，与 board 工具同源）：

- `GET /api/v1/memory/search?q=board&tag=office:board&limit=N&include_closed=true|false`
  - 实测返回 memories[]，字段：id/title/content/created_at/metadata，线上有真实帖子（2026-09-05 看板 M1 修复复盘帖等）。
- 帖子字段模型（源自 board-tools.ts 写入/读取逻辑）：
  - metadata.board_status ∈ {open, claimed, paused, blocked, done, dropped, archived}
  - metadata.kind ∈ {finding 发现, question 疑问, review 复盘, proposal 倡议}
  - metadata.author / metadata.assignee（窗口 id，w-xxx）；revision；claim_count；claimed_at；moderation_log[]；display_title（edit 时 title 存此）
  - needs_action=true → 初始 open（悬赏池）；false → 初始 done（纯记录）
- 状态机（STATE_MACHINE）：open→[claim,drop]；claimed→[pause,blocked,complete,drop]；paused→[claim,drop]；blocked→[claim,complete,drop]；done/dropped/archived 终态
  - UI「活跃集合」（= board_read 的 active 口径）= open/claimed/paused/blocked
- stale 派生口径（与 board_read 一致）：有 claimed_at 且超过 48h → stale；无 claimed_at 且创建超 72h → stale
- 路由冲突核查：execution 宿主已独占 /dashboard/api/board、holdings 独占 /dashboard/api/holdings → 新宿主路径用 **/dashboard/api/bulletin/***

## 3. 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| D1 | **v1 = 只读监控面板**，不做页面内写操作（认领/完成/删除/编辑全部仍走 board_update 工具） | 公告板是多写者（多窗口 agent + 人工）协作 + 状态机 + 乐观锁 revision + moderation_log 审计；写入职责属于 agent 工具链。页面只读可彻底规避绕过审计、并发写冲突 |
| D2 | 新插件包 @pi-investment/dashboard-bulletin，镜像 holdings 双半结构 | 页面域既有模式：host 同源 JSON API + client 侧栏入口 + 中心栏视图，含局部刷新教训 |
| D3 | 纯视图切换（状态 tab / kind pill / 翻页）只局部替换帖子卡根 id="dsh-bbd-posts"；仅数据拉取（刷新/轮询）才整体重绘 | 直接沿用 2026-09-05 持仓看板历史分页/盯盘 tab 修复的局部刷新策略 |
| D4 | Agent OS 不可达 → 正常 200 + degraded:true 信封，页面顶部降级 banner | 与持仓看板对 quantsys 的降级风格一致，避免整页白屏/红屏 |
| D5 | 展示排序 = created_at 降序（页面端重排），top_k 上限 200 | 引擎 search 语义检索返回序不稳定；200 是客户端上限，页脚注明范围 |

## 4. 包结构与文件清单

packages/pages/bulletin/（克隆 holdings 后全局替换命名空间 holdings→bulletin / dsh-hld-*→dsh-bbd-*）：

- package.json：name @pi-investment/dashboard-bulletin；exports "."→src/index.ts、"./client"→lib/client.js；dsh.client {platform: web, inject: [slots]}；scripts.build:client = tsdown + wrap
- src/index.ts（host）：name=dashboard-bulletin + apply；inject([webServer]) + effect 注册 exact /dashboard/api/bulletin/posts
- src/services/bulletin-aggregation.ts：fetch Agent OS memory search（include_closed 按需）→ 归一字段 → 信封 {success, data}
- src/routes/bulletin-routes.ts：query 解析（status/kind/assignee/page/page_size）→ 过滤 → stale/age 派生 → created_at 降序 → 内存切片分页 → counts 摘要
- src/types/index.ts + src/client/types.ts：BulletinData / Post / 状态与 kind 枚举（host/client 两端同步）
- src/client/index.ts：name/inject([slots])/apply；slots.inject(sidebar.footer.action) → register {id:dashboard-bulletin, order:300, label:公告板}（execution=100、holdings=200 之后）
- src/client/footer-action.ts：PANEL_NAME=dashboard-bulletin、PANEL_LABEL=公告板、OPEN_EVENT；公告板 glyph
- src/client/board-mount.ts：controller + 中心列 mount（container data-dsh-bbd-view，html[data-dsh-bbd-active] 显隐；ACTIVATE_EVENT 广播互斥——开公告板自动关持仓/执行板）；全局 __dshBbdRefresh/__dshBbdStatusTab/__dshBbdKind/__dshBbdPage
- src/client/view.ts：纯函数 buildBulletinCard(data, viewState)（帖子卡根带 id="dsh-bbd-posts"）+ 局部替换入口
- src/client/styles.ts：dsh-bbd-* 样式（与持仓板配色体系同源，--dsw-* tokens）

## 5. 宿主 API 契约

GET /dashboard/api/bulletin/posts?status=active|done|dropped|all&kind=finding|question|review|proposal&assignee=w-xxx&page=1&page_size=20

响应（信封与既有看板一致）：

```jsonc
{ "success": true, "data": {
  "posts": [{
    "id": "uuid", "title": "…", "content": "…",
    "status": "open", "kind": "finding",
    "author": "w-xxx", "assignee": null,
    "revision": 1, "claim_count": 0,
    "age_hours": 30, "stale": false,
    "created_at": "…", "claimed_at": null,
    "closed_at": null, "drop_reason": null,
    "moderation_log": []
  }],
  "total": 47, "page": 1, "page_size": 20,
  "counts": { "open": 3, "claimed": 2, "paused": 1, "blocked": 1, "done": 40, "dropped": 0, "archived": 0 },
  "degraded": false
}}
```

状态归一：页面端仅认 status 派生字段，不直接读 metadata。

## 6. UI 设计（中心栏全宽看板）

**Header**：标题「公告板」+ 数据源徽标 Agent OS + 状态计数胶囊（悬赏池 N · 待认领 x · 滞留超 48h y · 已完成 z）+ ↻ 刷新 + 30s 自动轮询（数据变更才整体重绘）。

**过滤条**：

- 状态 tab（值与 API status 契约同）：悬赏池(active) / 待认领(open) / 已认领(claimed) / 暂停(paused) / 卡住(blocked) / 已完成(done) / 已删除(dropped) / 全部(all)
- kind pill：全部 / 发现 / 疑问 / 复盘 / 倡议
- v1 展示列含认领人；不做 assignee 过滤下拉（简化）

**帖子流**（单列卡片，正文长不适用表格）：

- 左状态竖条色标 + kind 标签 + 「悬赏」徽标（open）+ stale 徽标「滞留超时」
- title（display_title || title，超长两行截断，title attr 全文本）
- content 3 行截断，点击卡片展开全文（手风琴）
- meta 行：作者窗口 · 认领人（未认领灰字）· 认领次数 · N 小时前 · revision vN
- moderation_log 时间线：详情展开后折叠展示（action/actor/timestamp/note）
- 色标：open=琥珀(待认领) · claimed=蓝(处理中) · paused=灰(暂停) · blocked=红(卡住) · done=绿(完成，整卡淡化) · dropped=删除线灰(终态) · archived=灰(仅 all 可见)
- 空态：当前筛选无帖子提示
- 分页：上/下一页 + 页码 + 每页 20 · **仅替换 #dsh-bbd-posts 卡根**（局部刷新铁律，不动 header/过滤条/其他面板）

## 7. 与既有页面的共存

- sidebar.footer.action 座位新增第 3 occupant（order 300），boot graph 加入 dashboard-bulletin
- 中心列 mount 独立命名空间（dsh-bbd-view），与 holdings（dsh-hld-view）各自为政，互不查询/互不替换对方 DOM
- 互斥打开：沿用 ACTIVATE_EVENT 广播（打开公告板 → 广播自身 panel name → 其他看板收到后自关；点会话行/侧栏行自动关板）
- 路由独占：/dashboard/api/bulletin/* 与 execution 的 /dashboard/api/board 无冲突

## 8. 验收标准

1. typecheck（host+client）+ build:client 绿；bundle 含 dsh-bbd-posts / dsh-bbd-* 标记
2. 宿主 curl /dashboard/api/bulletin/posts?status=all → 200、posts 非空（线上已有真实帖）、degraded=false、counts 与真实数据一致
3. 状态 tab / kind pill / 翻页均为局部替换：只换 #dsh-bbd-posts，header 与其他区域 DOM 不变（tsx 渲染隔离断言，方法同 holdings）
4. GUI 目检：侧栏出现「公告板」入口 → 打开渲染真实帖子；状态/分类/翻页/展开正常；与持仓、执行看板互斥开合正常
5. 降级路径：Agent OS 停止后页面显示 degraded banner 而非白屏/卡死
6. 关板/轮询/展开状态竞态无异常

## 9. 边界与风险

- top_k ≤ 200：帖子超过 200 时拉不全，页脚注明「仅展示最近 200 条」，不做深度分页（引擎侧搜索上限，二期可加服务端游标）
- 语义检索排序不稳：页面统一 created_at 降序重排，保证翻页稳定
- **只读边界是安全特性**：写入一律走 board_update（权限/审计/乐观锁完整），页面绝不直写 Agent OS memory
- 轮询合并：轮询拉到新数据时保留当前状态 tab/kind/页/展开项；被改动的帖子若正展开则安全折叠
- title/content 超长：截断 + title attr / 手风琴，避免布局撑破
