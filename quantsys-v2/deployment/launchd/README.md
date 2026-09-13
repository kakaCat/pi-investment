# deployment/launchd —— 指数日线采集（launchd 作业留档，2026-09-13，w-32314d00）

本目录保存 `~/Library/LaunchAgents/` 里与**指数日线采集**相关的 plist 原件，
以便"定时任务为什么长这样"可查、可复核、可重建（原先只存在于 ~/Library/LaunchAgents，
仓库里查不到，事故复盘时无法确认采集时刻）。

> ⚠️ 为什么不放 `scripts/launchd/`：`quantsys-v2/.gitignore` 第 22 行忽略了整个 `scripts/`
> （"One-off scripts & tools"），放那里等于**没进版本库**——而事故复盘的教训恰恰是
> "定时设置必须可查"。故留在已跟踪的 `deployment/` 下。

| plist | 时刻 | 作用 |
|---|---|---|
| `com.pi-investment.index-daily-refresh.plist` | 工作日 16:30 | best-effort：收盘后就采一次，通常只拿到 T-1（新浪当日 EOD 未发布） |
| `com.pi-investment.index-daily-refresh-final.plist` | 工作日 20:50 起，带 `--retry-until 23:15 --retry-interval 900` | 收尾：每 15 分钟重采，直到追平 `quant.daily_klines` 的 `market_latest`；到 23:15 仍未追平则 **exit 3**（fail-loud） |

## 为什么需要 final 作业

2026-09-13 处理的错误事件 `81d8f56c`（数据契约 `quant.index_daily:000300.SH`
freshness(market_latest)）根因就是**只有 16:30 那一趟**：

- 实测 2026-09-11 16:30 采集日志：8 个指数全部"最新 2026-09-10"（`logs/index-daily-refresh.log`）；
- 脚本对"数据是旧的"没有任何判定，**exit 0** → launchd 状态健康、无告警；
- `quant.index_daily` 静默停在 09-10，契约判定器（每日 23:40，
  `com.pi-investment.data-contracts-check`）在 09-11、09-12 连判两次 high 违约。

即"任务成功但数据没更新"——这类故障不会自己冒出来，必须让采集脚本自己判定新鲜度。

## 重装/检查

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
cp deployment/launchd/com.pi-investment.index-daily-refresh-final.plist ~/Library/LaunchAgents/
launchctl bootout  gui/$(id -u)/com.pi-investment.index-daily-refresh-final 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.pi-investment.index-daily-refresh-final.plist
launchctl print gui/$(id -u)/com.pi-investment.index-daily-refresh-final | head -20

# 手动补跑（幂等）
./venv/bin/python tools/backfill_index_daily.py --days 30 --require-fresh
```
