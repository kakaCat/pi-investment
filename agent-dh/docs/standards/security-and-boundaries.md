---
id: std-security-and-boundaries
title: 边界与安全规范（多实例 / 只读 / 显式降权）
type: standard
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [standards, safety, multi-instance]
---

# 边界与安全规范

**这页回答**：同机多实例、多账户、多窗口并行时，什么动作会伤到别人。

## 结论先行

1. **停实例必须精确到实例**：禁用 `pkill -f 'dsh web'` / `killall node`；`lsof` 查端口**必须**带
   `-sTCP:LISTEN`（否则会命中连着页面的浏览器进程）。每实例用 `stop.sh`（pidfile + 监听校验）。
2. **：13080 归 launchd**：重启 `launchctl kickstart -k`，停止 `launchctl bootout`；`kill` 会被
   KeepAlive 秒级拉起（表现为"停不掉"，随后手工启动必然 EADDRINUSE）。
3. **账户边界**：只写自己的账户（`agents.json` 的 `instance.account`）；`agent_virtual` 等只读账户
   **禁止写入**；不确定有哪些账户用 `account_list` 查，不靠记忆。
4. **权限/沙箱降级必须显式**：被拒绝（sandbox denied）就是拒绝，禁止换路径绕过；
   需要更宽权限时**同一命令**带 `sandbox_permissions` 重试一次并给理由。
5. **破坏性 git 操作前先归档**：任何 `checkout` / 覆盖 / 清空，先把现场存到具名 ref 并播报，
   绝不静默（历史：wip 独有文件被恢复流程静默抹除）。

## 关键机制

- 多实例端口表：:3080 主实例 / :13080 investment profile / :5001 quantsys-v2 / :8080 Agent OS(遗留)；
- `self_restart` 按 PID 精确停止，天然安全；手动停实例一律走该实例的 `stop.sh`；
- 并行窗口协作：改动走 worktree；重启前先确认会影响哪些窗口。

## 依据

- 2026-08-21 多实例铁律（模糊停止曾误杀其他 agent 进程）；
- 2026-09-11 `:13080` 被 kill 后 EADDRINUSE 事故；
- R-019 账户错位事故（默认值指错账户 = 用别人的账下单）。

## 自检清单

- [ ] 我要重启/停止的是哪个实例？命令精确吗（PID 或 launchd 标签）？
- [ ] 我要写的是哪个账户？名字来自事实源还是我写死的？
- [ ] 权限被拒后，我是停下来问/显式申请，还是在换着法绕过？
- [ ] 我要做的破坏性操作，现场归档了吗？通知到并行窗口了吗？

## 相关页面

- [账户与交易纪律](account-and-trading.md)
- [编码与协作规范](coding.md)
- [自修复重启行为](../architecture/self-restart-behavior.md)
- [重启与会话安全](../guides/restart-session-safety.md)
