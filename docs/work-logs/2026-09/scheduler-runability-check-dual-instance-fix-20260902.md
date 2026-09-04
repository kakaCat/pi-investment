# 定时任务可运行性全面检查 + 双实例双投风险处置（2026-09-02）

> 署名：investor w-8366e526 @ :13080 | 检查时间 21:10-22:00 CST

## 背景

用户要求确认"所有定时任务是否都能运行"。此前（同日）已完成调度双系统梳理：agent-os 只留 13 条 dsh-native（profit_engine 8 / autonomy 5），业务任务迁移至 quantsys-v2（APScheduler）。本次针对**可运行性**做执行级核验，并顺带发现/处置一个高危隐患。

## 检查结论（三个平面）

### ① v2 (quantsys-v2 APScheduler, :5001) — ✅ 30/30 可运行

- 30/30 任务 enabled 且均有 next_run_time（Python PID 1545, ~19:36 重启）
- 09-02 当日 94/94 次 job 执行成功（JobRegistry 启动 28 任务）
- 8-31 记录的"8 次失败"已定位：task 308 fund_flow_update 迁移中间态（IndentationError→ValueError），8-31 18:53 / 9-01 08:05 恢复，非系统性故障
- 9-01 的 232 条记录为重启孤儿产物，无实际影响

### ② agent-os 13 条 dsh-native（注册表在 agent-os :8080，真实执行在 DSH）— ✅ 可运行且已实证投递

- agent-os robfig cron 侧：任务 Command=/bin/true 但机器无 /bin/true（仅 /usr/bin/true）→ robfig fire 产生 fork/exec 噪音（无害，**非真实执行路径**）
- **真实执行者 = DSH lifecycle NativeReminderScheduler**（30s tick → 拉 agent-os dsh-native 任务 → cron 匹配 → 投递给在线 investor root）
- 实证：09-02 09:25:23 pre-market-routine、09:35:23 geer-take-profit-0901、13:00:19 afternoon-open-check-live 三次真实投递（DB memories office:delivered 佐证 + native-scheduler.json lastFired 佐证）
- 结论：13 条 dsh-native **能运行、今天确实运行过**；robfig /bin/true 噪音属观感问题（建议后续把 agent-os 侧 Command 清空/标 noop，或接受噪音）

### ③ 代码级检查 — 发现高危：双实例双投风险 → 已处置

**根因**：同机存在**两个 investment profile dsh 实例**，且共用同一份 `cordis.patch.yml`（含 lifecycle 插件段）：

| 实例 | PID | 端口 | runtime | 托管 | 启动时间 |
|---|---|---|---|---|---|
| 正式 | 7586→13741 | 13080 | rc.2/launchd | launchd KeepAlive | 19:47:37 → 21:58:47 重启 |
| 并行(孤儿) | 7902 | 13082 | 0.1.2-alpha.5 | 无 plist（被 launchd 收养 PPID=1） | 19:49:23 |

- 两实例都加载 lifecycle 插件（探测：两实例 `/wake` 均返回 401=路由存在+鉴权拒绝）→ **都无条件 setupNativeScheduler()**
- `native-scheduler.ts` 缺陷：state（lastFired）仅在**构造时读一次**进内存；tick 之间不重读文件；**无跨实例锁/单写者选举**
- ⇒ 同一 cron 分钟，两实例各自内存 state 都判"未 fire" → **双投**。首次暴露时间窗：09-03 09:25 pre-market-routine（随后 09:35 geer 止盈单不变量、16:05 signal-perf-verify-0903 一次性任务）
- 双投后果：pre-market 例程跑两份、**geer 止盈可能重复卖出**（不变量破坏）、一次性任务重复执行

**处置（用户确认后执行 22:00 前后）**：
- 用户确认：当前 GUI 在 13080；选择"停掉 :13082 (7902)"
- kill 7902 → 13082 停止 ✓
- 7586 同时退出（launchd KeepAlive 于 21:58:47 拉起新实例 **13741 (:13080)**），native-scheduler.json 21:58:49 被新实例重写 baseline
- **当前状态：单实例 13741 (:13080)，双投风险消除**

## 遗留建议

1. **agent-os 侧 13 条 dsh-native 的 Command=/bin/true**：fork/exec 噪音仍在（每次 robfig fire 打一条失败日志），建议改为空/占位命令或接受现状（无害但脏日志）
2. **native-scheduler.ts 单实例加固**（防未来再起第二实例）：
   - 方案 A（代码层）：tick 时重读 state 文件 + 基于文件写 lastFired 原子更新做跨进程去重
   - 方案 B（部署层）：cordis.patch.yml 给 lifecycle 加 enableNativeScheduler 开关，仅正式实例开
   - 建议后续用 candidate 观察版验证后转正（RFC 008 验证门）
3. 13082 实例来源未完全查明（疑为某次升级验证/测试遗留，19:49 启动、node_modules 同日 19:49 升级 alpha.5）——建议复盘启动链，避免再次出现孤儿实例

## 证据文件

- `~/.dsh/profiles/investment/state/native-scheduler.json`（lastFired 时间线）
- `agent-os/logs/launchd-stdout.log`（robfig 噪音 / webhook 成功记录）
- `/private/tmp/dsh-alpha5.log`（13082 实例 banner）
- DB `public.memories` office:delivered 记录（09-02 三次真实投递）
