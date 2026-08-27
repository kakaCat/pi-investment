# Watch 告警链路静默失效排查与修复（2026-08-24）

## 事件

002241 歌尔股份两条盯盘规则（#38 真实账户止盈 23.9、#49 模拟仓止盈 24.4）在 2026-08-24 09:30-10:46 触发约 18 次（盘中最高 24.80），但 `notified=false`、`agent_response=null`，Agent 未被唤醒，最佳止盈窗口静默错过。

## Root Cause（三层叠加）

1. **主因（代码 bug）**：`agent-ts/src/api/gateway/adapters/wake-adapter.ts` 在主分支上被提交了语法错误——`registerRoutes` 方法声明重复 + 类结尾多余 `}`。导致 `npm run wake` 启动即崩溃（esbuild TransformError），wake channel 3002 长期无进程监听。
2. **架构特点**：TUI 主会话（`npm run dev` / src/index.ts）**不启动** wake gateway，3002 由独立进程（`npm run wake` / `npm run headless`）提供。wake 进程崩了 = 整条告警链静默死亡，TUI 会话毫无感知。
3. **次生灾害**：web-frontend 被手动重复启动（与 launchd 任务 `com.pi-investment.web`（keepalive）并存），第二个 vite 因 3001 被占自动递增抢占 3002（绑 [::1]），kill 后 launchd 会立即复活抢端口。

## 后端行为（quantsys-v2，无 bug 但值得记录）

- `application/services/watch_engine/notifier.py` → `agent_notification_service.py`：`POST {AGENT_API_URL=http://127.0.0.1:3002}/wake`，重试 3 次（间隔 1s），最终失败落库 `notified=false` 并日志"已落库待补发"。
- `timeout` 视为成功（wake 同步等 LLM 决策，超时是常态）。

## 修复

1. worktree `feat/fix-watch-notify` 修复 wake-adapter.ts 语法错误（删 5 行重复代码），已合并 main 并删除 worktree。
2. 清理端口：杀掉手动重复启动的 vite 树，launchd 复活实例正常独占 3001；wake 进程从主目录重启，健康检查通过，`POST /wake` 端到端验证 success:true。
3. wake 当前以后台进程运行（`nohup npm run wake`，日志 /tmp/agent-wake.log）。**注意：重启机器/会话后需手动重启 wake 进程**，建议后续纳入 launchd 管理（尚未做）。

## 遗留问题（未修，已记 memory）

- quantsys-v2 `/api/simulation/accounts/{name}` 500（SimulationService.repo=None），portfolio_status(get)/portfolio_analyze 全账户不可用；trades/list 接口正常可推算持仓。
- 投资脑（agent-dh）飞书报告数据口径混乱：总资产取 agent_virtual 但收益/回撤/夏普对不上（+4.55% 写成 -4.2%）。
- V2MemoryProvider 500（'dict' object has no attribute 'app'），wake 进程降级 file-fallback。
- web-frontend vite.config 未设 strictPort，端口被占时会漫游抢 3002（建议加 `strictPort: true`，未做）。
- 今晨 18 条触发记录不会自动补发，歌尔止盈决策需人工处理。
