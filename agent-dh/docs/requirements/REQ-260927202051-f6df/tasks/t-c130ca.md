# t-c130ca 看板实测回归（真实打开页面）·研发

> 需求：REQ-260927202051-f6df 实现 DAG 任务队列机制（拆分时生成 queue.json）

## 在做什么
看板实测回归（真实打开页面）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

真实打开页面并可复核：`cd agent-dh && node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req REQ-260927202051-f6df --out docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart` → 退出码 0、15 passed / 0 failed；产出 shots-after-restart/SUMMARY.json + 4 张 PNG。判据：命令 + 断言数 + 截图路径贴进卡文档（禁止以 curl 200 代替渲染验证）。

## 汇报 1（2026-09-27T16:03:19.678Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

研发实测做完：在**投产后的实例**上真实打开看板 4 个页面，15/15 断言全过并落 4 张截图。这一步让「看板不回归」从"待实测"变成有真实渲染证据（不是 curl 200）。

### 完成项

- 真实浏览器实测（headless Chrome + CDP）：泳道看板/列表视图/任务总览+甘特/需求详情 4 个页面全部真实加载，断言取自渲染后 DOM —— 15 passed / 0 failed（断言含：泳道 6、需求卡 34、列表 10、任务总览 51 组 616 行、甘特 SVG 在场、本需求卡片与分组命中、DAG 11 层、页面异常/console.error/失败请求 0、接口 tasks=616 requirements=82）
- 落盘 4 张真实渲染截图（1680×1413）+ 结构化证据 SUMMARY.json
- 页面可达性探针 4/4：GET /(带 cookie)→200 且 pmboard 命中 5；无 cookie→401；GET /dashboard→404（客户端 hash 路由，服务端无此 path —— 卡内验收①的字面命令口径问题由此暴露）；/dashboard/api/reqboard/state→200 requirements=82 tasks=616
- 队列/读方单测非回归：npx vitest run packages/web/dsh-pmboard/tests/queue → 12 files / 131 passed
- 被测对象先钉事实：pid/启动时刻/dist 构建时刻/台账 schemaVersion=9 且无 tasks 键/51 份 queue.json 616 条任务；启动日志 LEDGER_REQUIRES_MIGRATION=0、未捕获异常 0
- 与重启前一轮（23:19）逐项对照：结构性计数全同（泳道 6 / 卡 34 / 列表 10 / 51 组 616 行 / 甘特 / 详情表与 Tab / DAG 11 层），仅 rev 与正文长度随运行期活动漂移

### 改动文件

- `docs/requirements/REQ-260927202051-f6df/notes/board-live/run-report-after-restart.md`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/run-after-restart.console.log`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.console.log`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart/SUMMARY.json`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart/01-board-lanes.png`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart/02-board-list.png`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart/03-tasks-gantt.png`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/shots-after-restart/04-req-detail.png`

### 下一步

联调卡（t-6df9a0）把接口出数与磁盘真值逐项对齐。

---
