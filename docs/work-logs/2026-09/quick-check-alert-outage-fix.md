# 盘中快检：market_alert 接口故障定位与修复（2026-09-08 11:00）

## 背景

盘中快速检查（scheduled task）执行时发现 `market_alert` 接口持续超时，与 02:21 快检记录的故障一致，至 11:00 仍未恢复。本记录固化关键发现与已实施的修复，防止上下文压缩后丢失。

## 快检结果

### 1. market_alert（预警接口）❌ 故障

- `/api/alerts/check` 与 `/api/alerts/statistics` 均超时（curl 30s / 8s 探测均 http_code=000，无响应）。
- 自 02:21 诊断记录以来持续 9+ 小时未恢复，盘中预警盲区。

### 2. portfolio_status（账户）✅ 正常

7 账户全部 `active`，无异常：

| 账户 | 总资产 | 累计收益率 | 持仓数 |
|------|--------|-----------|--------|
| v14_simulation | 46,880 | -53.12% | 4 |
| agent_brain | 99,918 | -0.08% | 1 |
| v15_simulation | 100,000 | 0% | 0 |
| chip_simulation | 100,000 | 0% | 0 |
| user_main_simulation | 201,599 | +0.80% | 3 |
| agent_virtual | 105,049 | +5.05% | 3 |
| v13_simulation | 84,850 | -15.14% | 4 |

注：v14_simulation 累计 -53.12% 为策略模拟实验账户（v13 亦 -15.14%），非实盘，快检未深入。

### 3. watch/triggers（替代渠道）✅ 有触发但非持仓

今日盘中触发：600026 多次下破（20.0/19.85）、002463.SZ 上破 120.8、002815.SZ 上破 14.9。
经核对这些 symbol **均不在任何账户持仓中**（持仓为 300224/300226/300229/300889/002007/600036/601600/300677/600887/601288/300888），属候选观察股，无 T+1 可操作事项。

## 根因定位（已读源码确认）

`GameAlertService.check_alerts()` → `_check_manipulation_alerts()` → `ManipulationDetector.detect_market_manipulation()` → `_scan_potential_manipulations()`：

1. `_get_recent_zt_stocks()` 调 `provider_manager.get_zt_pool()`（akshare `stock_zt_pool_em`，东财网络请求）。
2. 对最多 50 只涨停股逐个调 `_detect_manipulation_signals()` → `_check_lhb_hot_money()`（akshare `stock_lhb_detail_em`，龙虎榜）+ `_check_volume_surge()`（DB，快）。

数据源管理器 `_try_providers` 虽有 60s/调用超时 + 熔断器，但**逐股串行**导致总时长无上限（50 股 × 60s+），`/api/alerts/check` 路由同步调用因此无限挂起。agent 侧 `runQuantV2` 30s 超时放弃，但后端 handler 仍在后台持续消耗。

对手行为分析（opponent-behavior）本身正常（记忆记录 0.013s，degraded=true 资金流无数据），非挂起点。

## 已实施的修复（worktree 隔离）

分支：`fix/alert-manipulation-timeout`（worktree: `.claude/worktrees/fix-alert-timeout`）

### `quantsys-v2/application/services/manipulation_detector.py`

- `__init__` 新增 `scan_timeout_seconds=15.0`、`max_scan_stocks=20`。
- `_scan_potential_manipulations()` 循环内加 `time.monotonic()` 截止检查，超预算即 break 降级。
- `_get_recent_zt_stocks()` 限制 `stocks[:50]` → `stocks[:self.max_scan_stocks]`。

### `quantsys-v2/application/services/game_alert_service.py`

- `__init__` 新增 `manipulation_timeout_seconds=20`。
- 新增 `_run_with_timeout()` 辅助（ThreadPoolExecutor + `fut.result(timeout=...)` + `shutdown(wait=False)`，与 `manager.py::_try_providers` 同模式，finally 中 `close_session()` 防 session 泄漏）。
- `_check_manipulation_alerts()` 用 `_run_with_timeout` 包裹 `detect_market_manipulation()`，超时返回 None → 跳过操纵预警（降级），保证 `/api/alerts/check` 端到端有硬上限。

## 验证状态

- ✅ 两文件 `py_compile` 通过。
- ✅ `_run_with_timeout` 超时逻辑验证：slow_fn(5s) 在 1s 超时下 1.01s 返回 None（未等满 5s）。
- ✅ 端到端验证（2026-09-08 12:03，worktree 代码 + main venv 直接调用 `GameAlertService().check_alerts()`）：**12.97s 返回 0 预警**（未无限挂起），`_run_with_timeout`/扫描预算均在位。注：验证环境未注入 repos（`get_fund_flow` 返回 None、降级路径），未复现 akshare 真实网络挂起，但两层硬上限（外层 20s + 内层 15s/20 只）已覆盖该场景。
- ✅ **已合并 + 推送**（2026-09-08 12:31 快检轮）：`git merge --ff-only fix/alert-manipulation-timeout`（fast-forward，b0319187 → a4b70536），`git push origin main` 成功。分支仅领先 main 1 commit、仅改 2 文件（`game_alert_service.py`/`manipulation_detector.py`），与主工作区脏改动零重叠。

## 生产后端重启（⚠️ 仍待执行，被其他会话脏改动阻塞）

合并后**尚未重启**生产 5001（PID 4154，9:51 AM 启动 `adapters/inbound/fastapi_app/main.py`），故线上 `/api/alerts/check` 仍超时。

**阻塞原因**：主工作区存在其他会话在 9:51 AM 之后修改的脏文件，直接重启会连带加载这些半成品代码到生产进程：

- `watch_rule_repository.py`（12:27 改）
- `watch_engine/engine.py`（12:10 改）
- `daily_jobs_bootstrap.py`（12:08 改）
- `notification_facade.py`（11:07 改）、`watch_engine/factory.py`/`notifier.py`（11:09 改）

**正确路径**：待这些会话（watch-engine RFC 011 分层通知等）完成并提交后，再做一次干净的、协调的重启，一次带出修复 + 他人已完成工作。

## 待办 / 后续

1. ~~合并 `fix/alert-manipulation-timeout` → main → push~~ ✅ 已完成（2026-09-08 12:31）。
2. **重启生产后端**：待其他会话 watch-engine 脏改动提交后协调重启，勿在脏工作区直接重启（会把半成品 watch_engine 代码带上线）。重启后可验证 `/api/alerts/check` 返回（预期 ≤20s 硬上限，非无限挂起）。
3. 建议后续为 `get_lhb_detail`/`get_zt_pool` 这类单调用设置更短超时（当前 60s 对预警场景仍偏长），并评估在 `check_alerts` 入口加结果缓存/降级缓存，避免每次请求都实时扫描。
