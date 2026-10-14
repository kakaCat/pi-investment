# t-b17ab4 卫生债批量清理（550 处）·联调

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
卫生债批量清理（550 处）·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-01T13:49:02.476Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

联调段：**用新代码把服务重启起来了**（101 条路由、图表接口返回真实的 09-30 行情、探针判为新鲜），证明这三批卫生债改动没有伤到启动链路；过程中还撞出并坐实了一个**文档与代码不一致的启动陷阱**——仓库文档写的启动命令少了 `PYTHONPATH=.`，照抄会直接起不来。

### 完成项

- **联调①：用新代码（主题A+B+C）重启服务成功**——PID 12604、ppid=1（daemon 化）、`/docs=200`、健康探针 exit=0；这是对"主题B 改掉启动期日志配置"最有力的验证（服务真的起来了）
- 联调②：`from adapters.inbound.fastapi_app.main import app` 成功，**路由数 101**；root logger handlers = [StreamHandler, AgentOSErrorLogHandler]——应用自行配置日志的链路完好，不再依赖任何库层 basicConfig
- 联调③：两个改动过的 job 入口齐备（index_constituents 的 `execute`、strategy_risk_check 的 `strategy_risk_check`/`all_strategies_risk_check`/`v13_risk_check` 等）
- 联调④：改过运行说明的迁移按**文档命令**真跑——`PYTHONPATH=. python .../20260911_index_daily_split.py` 与 `recompute_account_max_drawdown_20260911.py` 均输出 dry-run 提示（未落库）
- 联调⑤：端到端数据链路在新代码下正常——`GET /api/charts/kline/600519` 返回**真实 2026-09-30 行情**；探针显示 factor_latest=2026-09-30、lag_days=1 ≤ max_lag_days=1（新鲜）
- **坐实一个运维陷阱（非本卡引入，但值得报）**：CLAUDE.md 第 133/189 行记载的启动命令 `python adapters/inbound/fastapi_app/main.py` **实际跑不起来**——报 `ModuleNotFoundError: No module named 'adapters'`。原因是 main.py 自己的 `sys.path.insert`（第 33 行）**晚于**它在第 24 行对 `adapters.*` 的导入，那行路径代码对自己的导入是死代码；真实启动必须额外 `PYTHONPATH=.`（文档未写）。我第一次重启就是踩了这个坑（服务曾短暂 down 约 1 分钟，已用正确环境拉起恢复）
- 重启过程中的自我纠错：第一次用 `exec(open(main.py).read())` 导致 `NameError: __file__`（exec 无 `__file__`）→ 改用双 fork + setsid + **execv** 保留 argv/__file__ 才成功；随后补 `PYTHONPATH=.` 恢复服务

---
