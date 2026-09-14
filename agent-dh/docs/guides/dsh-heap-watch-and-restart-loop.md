---
id: guide-dsh-heap-watch-and-restart-loop
title: DSH 内存看门狗与「反复重启」判别（10 分钟一轮）
summary: 每 10 分钟整点重启 = dsh-heap-watch 超阈值自动重启，不是崩溃；含机制、2026-09-14 实测根因、退避围栏与处置步骤。
type: guide
status: living
updated: 2026-09-14
owners: [w-175cf88f]
tags: [guide, ops, heap-watch, restart, dsh]
---

# DSH 内存看门狗与「反复重启」判别

**这页回答**：agent-dh 为什么每隔 10 分钟就重启一次？是崩了还是被谁重启？内存怎么会冲到 7.6GB？收到「看门狗退避」告警后该做什么？

## 一句话判别

> **每 10 分钟「整点」重启一次 = `dsh-heap-watch` 内存看门狗超阈值自动重启，不是崩溃。**
> 崩溃（OOM）是随机时刻、日志里有 `FATAL ERROR: Reached heap limit`；被看门狗重启是**固定 10 分钟节拍**、日志里有 `AUTO_RESTART=1 → launchctl kickstart -k`。

| 观察点 | 崩溃 / OOM | 看门狗重启 |
|---|---|---|
| 间隔 | 随机（数分钟到数小时） | **固定 10 分钟**（`StartInterval=600`） |
| 日志 | `FATAL ERROR: Reached heap limit` | `[dsh-heap-watch] 超阈值：... → kickstart` |
| 触发值 | 撞上 V8 上限瞬间 | RSS 达阈值（堆上限的 75%） |
| 处置 | 查泄漏 | 见本文「处置手册」 |

## 一、证据怎么取（三条命令）

```bash
# 1) 重启节拍：看 launchd 时间线（是否有 10 分钟整点的 service inactive）
log show --last 2h --style compact --predicate 'process == "launchd" AND eventMessage CONTAINS "com.pi-investment.dsh"'

# 2) 谁在重启：看门狗自己的日志（超阈值 + kickstart 都记在这里）
tail -20 /Users/yunpeng/pi-investment/logs/dsh-heap-watch.log
tail -10 /Users/yunpeng/pi-investment/logs/dsh-heap-watch.err.log

# 3) 台账：近 1 小时自动重启了几次（REQ-dfd8b6 新增）
cat /Users/yunpeng/pi-investment/logs/dsh-heap-watch-restarts.tsv
tail -30 /Users/yunpeng/pi-investment/logs/dsh-heap-watch-guard.log
```

## 二、机制：谁在重启、阈值怎么定

- **作业**：launchd `com.pi-investment.dsh`（KeepAlive + RunAtLoad）跑 `agent-dh/scripts/start.sh 13080`；`start.sh` 用 `exec` 拉起 node，所以**作业 pid 就是 node pid**。
- **看门狗**：launchd `com.pi-investment.dsh-heap-watch` 每 `600s` 跑一次 `scripts/dsh-heap-watch.sh`：取 `:13080` 的 LISTEN 进程 RSS，超过阈值且 `AUTO_RESTART=1` → `launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`（**唯一安全入口**：kill 会被 KeepAlive 秒级拉起并与新进程抢端口）。
- **阈值自适应**：脚本读进程的 `--max-old-space-size`（`NODE_OPTIONS`，由 `start.sh` 的 `DSH_MAX_OLD_SPACE` 决定），取 **75%** 作阈值（不低于 plist 配置的 6144）。堆上限 8192 → 阈值 6144；堆上限 16384 → 阈值 12288。
- **通道不可用就不 kill**：launchd 作业不在域内时只告警——宁可高内存实例多活一会儿，也不能杀了拉不起来。

## 三、为什么内存会冲到 7.6GB（2026-09-14 实测）

| 观测 | 数值 | 来源 |
|---|---|---|
| 三次重启触发值 | RSS 7632 / 7717 / 7674MB（上限 8192MB） | `logs/dsh-heap-watch.err.log`，2026-09-14 22:45–23:05 |
| 重启节拍 | 22:45:31 / 22:55:35 / 23:05:40（各 +10min） | `log show` launchd 时间线 |
| 会话库体积 | `.dsh-data/sessions` = 881MB / 263 个会话；单会话最大 113.8MB | `du` / `find -size`，2026-09-14 23:10 |
| 投影缓存重建 | 22:56 一次写 **62 个投影**，对应压缩会话 **714.8MB** | `storages/session_projcache/sessions` 文件 mtime 分布 |

**因果链**：DSH 是多窗口共享单进程；实例重启后要**重建 session projection cache**（会话历史要被解压/投影落盘）→ 重建峰值把 RSS 顶到 7.7GB，贴着 8GB 的 V8 上限 → 10 分钟后看门狗超阈值 → kickstart → 新实例再重建 → **重启 → 重建 → 再超阈值** 的自持循环。
22:56 那次重建把 62 个投影落盘完成后，23:05 起的实例命中热缓存，RSS 一路回落到 672MB（23:15 采样），循环自行终止。
诱因：当日 DSH_HOME/profile 迁移（19:55 / 21:56 / 22:41 三次）令既有投影缓存失效，必须全量重建。

> 结论：**看门狗没有错**（它防的是真正的 OOM）；错的是「重建峰值 + 旧版无退避、无告警」。所以修复分两头：给峰值留头寸，给看门狗加围栏。

## 四、本次修复（REQ-dfd8b6，2026-09-14）

### 1) 看门狗退避围栏（`scripts/dsh-heap-watch.sh`）

| 能力 | 行为 |
|---|---|
| 重启台账 | 每次真实重启追加 `logs/dsh-heap-watch-restarts.tsv`（`ts / rss / 旧pid / 新pid`），保留 24h |
| 每小时上限 | 滚动 1 小时内达 `MAX_RESTARTS_PER_HOUR`（默认 3）仍超阈值 → **退避**：只告警不再重启；`ALLOW_RESTART_BEYOND_CAP=1` 为逃生阀 |
| 告警升级 | 单次重启 = error 事件（原行为）；1 小时内第 2 次起 → `alerts` 群 **high**，内容含近一小时轨迹 + 最重的 5 个会话 |
| 恢复即清零 | RSS 回落到阈值以下 → 台账窗口作废（判定重启有效），下次重新计数 |
| 零副作用钩子 | `HEAP_WATCH_DRY_RUN=1`：只打印将执行的动作，不重启、不外发、不写台账 |

### 2) 内存上限留头寸（`agent-dh/.env`）

`DSH_MAX_OLD_SPACE=16384`（默认 8192 → 阈值 6144 会被重建峰值顶穿；64GB 机器给 16GB 上限，阈值自适应为 12288，实测 7.7GB 峰值不再触发重启）。
`.env` 由 `start.sh` 启动时 source，**下次重启生效**；改动不入库（`.env` 在 `.gitignore`），故在此登记。要回退：删掉该行即可回到 8192。

## 五、验证（怎么证明改对了）

故障注入（全程旁路：`HEAP_WATCH_DRY_RUN=1` + `HEAP_WATCH_STATE_DIR=/tmp/...`，实例 pid 与 launchd `runs` 不变）：

```bash
# 正常水位不动作
FORCE_THRESHOLD=1 THRESHOLD_MB=100000 HEAP_WATCH_DRY_RUN=1 HEAP_WATCH_STATE_DIR=/tmp/hw-A \
  bash scripts/dsh-heap-watch.sh
# 超阈值但台账为空 → 允许重启（打印将 kickstart）
FORCE_THRESHOLD=1 THRESHOLD_MB=1 AUTO_RESTART=1 HEAP_WATCH_DRY_RUN=1 HEAP_WATCH_STATE_DIR=/tmp/hw-B \
  bash scripts/dsh-heap-watch.sh
# 预置 3 条近 1 小时台账 → 退避，不再重启
printf '%s\t7600\t111\t222\n' "$(date +%s)" >> /tmp/hw-C/dsh-heap-watch-restarts.tsv   # ×3
FORCE_THRESHOLD=1 THRESHOLD_MB=1 AUTO_RESTART=1 HEAP_WATCH_DRY_RUN=1 HEAP_WATCH_STATE_DIR=/tmp/hw-C \
  bash scripts/dsh-heap-watch.sh
# 重启通道不可用 → 只告警，绝不 kill
FORCE_THRESHOLD=1 THRESHOLD_MB=1 AUTO_RESTART=1 DSH_LAUNCHD_LABEL=com.pi-investment.__no_such_job__ \
  AGENT_OS_BASE_URL=http://127.0.0.1:9 HEAP_WATCH_STATE_DIR=/tmp/hw-F bash scripts/dsh-heap-watch.sh
```

2026-09-14 实测：**20 项断言全 PASS**，且实例 pid（25727）与 launchd `runs`（6）在测试前后不变（零副作用）。

## 六、处置手册（收到告警 / 看到循环）

1. **先确认是不是看门狗**：`tail logs/dsh-heap-watch.log`；有 `AUTO_RESTART=1 → kickstart` 即是。
2. **不要 kill 实例**：:13080 归 launchd 管，`kill` 会被 KeepAlive 拉起并抢端口。要重启走 `launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`。
3. **退避告警（1 小时 ≥3 次）意味着「重启不再有收益」**：
   - 看报警正文里的「最重的会话」——投影重建是全量解压，大头就在这里；
   - 需要长期压峰值时按需归档超大历史会话（**先备份再动**，属于数据动作，需人工确认）；
   - 实例仍在使用中：退避期间它可能真的撞上 8GB 上限 OOM，此时 launchd KeepAlive 会重新拉起（等价于一次重启），但**不会**再被本脚本按 10 分钟节拍反复打断。
4. **循环停止的判据**：`logs/dsh-heap-watch-guard.log` 出现「内存已回落…判定为**有效**，台账清零」。

## 相关页面

- [故障排查手册（症状 → 根因 → 处置）](troubleshooting.md) —— A 节「服务与端口」
- [自修复重启行为](../architecture/self-restart-behavior.md) —— `self_restart` 工具本身
- [重启与会话安全](restart-session-safety.md) —— 重启后会话历史为什么不丢
- [启动](STARTUP.md) —— 启动入口与 `DSH_MAX_OLD_SPACE`
- [定时巡检清单](routine-checks.md) —— 例行检查项
