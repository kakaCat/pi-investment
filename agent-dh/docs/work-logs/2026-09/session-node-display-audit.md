# 会话框节点展示内容审计 —— 以 REQ-4842fe 源会话为例

> 审计窗口：w-85447f15（investor）｜ 审计日期：2026-09-21
> 样本会话：session-d41c9696-eb63-4a47-9018-68884d1f1fc8（REQ-4842fe「重构 task_execute」的立项与实施会话）
> 方法：解压 session.v3.jsonl.zstd 全量事件（4127 条）+ 对照 dsh-client-ui-chat / dsh-client-ui-tool 渲染源码逐类核实

## 1. 会话节点全景

| 指标 | 数值 |
|---|---|
| turn / step | 18 / 427（turn 12 单 turn 158 step，turn 9=69，turn 17=93） |
| run_code 根工具节点 | 410（全部工具调用都走 run_code 包装） |
| 内层 ptc-dispatch 子调用 | 905（edit 243 / bash 240 / read 130 / reqboard_* 137 / write 56 / grep+glob 49 / ask_user_question 23 / todo_write 13 / 其他 14） |
| assistant 消息 | 425（含正文 text 仅 111，纯工具调用 314） |
| reasoning / 正文 text 体量 | 914KB / 39KB（23:1） |
| user / system 消息 | 30 / 42 |
| run_code 根节点失败 | 29；子调用错误 37（reqboard_task_move 17、reqboard_submit 7、edit 5…） |

## 2. 渲染链路（源码核实结论）

会话框把 `tool/call` + `tool/result` + `tool/ptc-dispatch(-start)` 投影成一棵 tool-call 树
（dsh-client-ui-chat，嵌套上限 MAX_DEPTH=256）。树上每个调用节点经 `tool.call.toolview` keyed
插槽分发：**有专用 toolview 的用专用卡片，没有的一律回落 GenericToolCard**。

GenericToolCard 按工具名分 variant：

| variant | 工具 | 行内展示 |
|---|---|---|
| code | run_code | summary=description 参数；展开体=代码全文；输出=程序 print/return |
| bash | bash/pwsh | 终端卡（命令+输出，224px 滚动） |
| read | read/read_image/web_fetch | 读取卡（路径可点击打开） |
| write/edit | write/edit | diff 卡（前后对比+增删统计） |
| search | grep/glob/web_search | 搜索卡（命中列表） |
| **others** | **其余全部（含 agent-dh 所有业务工具）** | **summary = `工具名 · args 里第一个非空字符串参数的首行`；输出=结果纯文本（pre-wrap，260px 滚动）** |

其他节点类型：assistant 正文/思考块（reasoning 折叠）、user 消息、system 消息、inbox、
request-prompt、turn 错误/截断提示均已注册渲染；**todo_write 没有会话内专用节点**（仅在
host/controller 层持久化，会话里只是 57B 的通用工具行）。

**无截断**：输出区靠 CSS 滚动（bodyScroll 260px / ioSection 150px），内容全量渲染。
本会话最大单节点输出 126KB（run_code 根）、业务工具最大 20.7KB（notification_channels 裸 JSON）。

## 3. 发现的问题（按严重度）

### P1-1 业务工具节点折叠态零信息量、互相无法区分
`others` variant 的 summary 取 args 中**第一个字符串参数**。reqboard_task_move 的
args={task_id, to, reason}，键序使 task_id 永远胜出——本会话 **76 行折叠态全部长一样**：

```
reqboard_task_move · t-b0b327      （实际是 to=in_progress）
reqboard_task_move · t-b0b327      （实际是 to=done）
reqboard_task_move · t-b0b327      （实际是 to=testing）
…
```

用户在会话框里无法看出"任务被推进到了哪个状态"，必须逐行展开。同类问题覆盖全部 187 个
others 节点（reqboard_submit/ask_confirm/status、decision_audit、memory_write…）。
根因：框架层 SUMMARY_KEYS.others=[] 且不支持 per-tool 配置；agent-dh 工具无一注册 keyed toolview。

### P1-2 业务工具结果 = 裸 JSON 文本墙
agent-dh 插件的 output.render 清一色 `JSON.stringify(value, null, 2)`（全仓 39 处 +
pmboard 的 renderJson）。GenericToolCard 的输出区是纯文本 pre-wrap，不渲染 markdown/结构：
reqboard_status 平均 1.9KB、board_read 14KB、notification_channels 20.7KB 的 JSON 直接糊在
节点里。人读困难，且与"行内摘要"无任何呼应。

### ~~P2-1 todo_write 计划内容不可见~~（2026-09-21 复核修正：结论错误）
**复核更正**：dsh-client-ui-tool 实际注册了 key=`todo_write` 的专用 toolview
（todo-row.js，L2299-2305），解析 argsRaw.todos 渲染"完成数/总数 · 当前进行中项"
（如 `3/13 已完成 · 实现 task_execute`），本会话 13 次 todo_write 在 GUI 中有专用行。
原结论误因：只 grep 了 `"todo/` 事件模式，漏掉 toolview keyed 注册路径。教训：审计 UI
行为需同时查"事件渲染"与"toolview keyed 注册"两条路径。真正缺失的是**会话级固定进度
面板**（非每行工具卡），降级为低优先观察项。

### P2-2 超长 turn 形成"工具节点墙"
turn 12 = 158 个连续 step ≈ 158 个 run_code 节点顺序排列；turn 9/17 分别 69/93。
无分组、无折叠、无分页。与 REQ-4842fe 要解决的"长任务"问题是同一枚硬币的展示面。

### P2-3 run_code 根输出与子调用输出重复
agent 习惯把子调用结果 console.log 出来，导致同一段文本在父节点（中位 770B，p90 4.9KB）
和子节点各显示一遍，放大节点墙体量。

### P3 others 无字符串参数时 summary 退化为 JSON 原文首行
deriveSummary 兜底 firstLine(argsRaw)，显示一段 JSON 残片，无信息量且误导。

### ✅ 做得好的部分
- run_code / bash / edit / read / search 五类 variant 卡片信息完整、可读性好（243 个 edit
  全是 diff 卡，121B 精确摘要）
- ask_user_question 有专用问答卡（本会话 23 次弹框问答均可回溯问题与所选答案）
- 错误可见性合格：错误行红标 + 首行 errorSummary（17 个 reqboard_task_move 拒绝一眼可辨）
- reasoning 折叠、无内容截断、中断有 interrupted 合成节点

## 4. 改进建议（按成本排序）

| # | 改动 | 落点 | 成本 | 解决问题 |
|---|---|---|---|---|
| 1 | 框架 SUMMARY_KEYS 支持 per-tool 配置，为 reqboard_* 等高频工具指定摘要键（to/action/title/symbol） | dsh-client-ui-tool（DSH 主仓） | 低 | P1-1、P3 |
| 2 | 为 reqboard_* 高频工具注册 keyed `tool.call.toolview`（状态迁移行/确认卡/清单卡） | pages/dsh-pmboard client 侧（页面插件本就有 client bundle 机制） | 中 | P1-1、P1-2 |
| 3 | ~~todo_write toolview~~（框架已有，复核修正）；会话级固定进度面板如需另行立项 | — | — | — |
| 4 | 业务工具 render 约定"首行=人读摘要，后附 JSON"（GenericToolCard 输出区与 errorSummary 都取首行，零框架改动即可获益） | agent-dh 各插件 renderJson | 低 | P1-2 部分缓解 |
| 5 | 长 turn 节点分组/折叠（如每 20 个连续工具节点自动折叠为一组） | DSH 主仓 chat UI | 高 | P2-2 |
| 6 | run_code 编程习惯：不整段 echo 子调用结果，只打印增量结论 | agent 行为/提示词 | 低 | P2-3 |

## 5. 数据口径

- 事件源：`.dsh-data/sessions/--Users-yunpeng-pi-investment-agent-dh--/session-d41c9696…/session.v3.jsonl.zstd`（4127 条事件，zstd 流式解压）
- 渲染源码：dsh-web-app@0.1.5-rc.1 checkout 内 dsh-client-ui-chat/lib/client.js（节点投影，L6287-6560）、dsh-client-ui-tool/lib/client.js（GenericToolCard/toolRowModel，L760-1000、L1389-1428）
- variant 分类与 SUMMARY_KEYS 逐行核对于 toolRowModel（L951-973）与 TOOL_VARIANTS（L794-815）
