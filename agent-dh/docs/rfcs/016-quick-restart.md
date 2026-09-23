# RFC 016: quick_restart —— web-liveness 轻量重启工具

- **状态**：已实施（2026-09-23，088ef4e3 + 健康判定修复 278a9e53）
- **作者**：Claude（与用户共创）
- **关联**：RFC 002（self_restart 发版重启）、2026-09-22 重启入口收敛（42159f56）

## 背景

2026-09-22 用户裁定 :13080 重启入口收敛为 `scripts/stop.sh` + `start.sh` 唯一一套（launchd 全部退役）。
2026-09-23 凌晨一个 `launchctl submit` 死循环（tmp-restart）杀了所有实例 10.7 小时，用户早晨无法启动——
说明"重启"这个动作需要一个**受控的、agent 可调的、不产生第二份逻辑**的入口。

agent 已有 `self_restart`（lifecycle 插件），但它是**发版场景**的重型工具：wip 检查点、git 回滚、
自动续跑。日常场景（让改动生效、状态异常自救）不需要这些语义，缺一个轻量重启工具。

## 目标

agent 可调用的轻量重启工具 `quick_restart`，与 web-liveness 的页面自愈能力天然衔接：

- 重启后页面自动出"服务重启中"横幅（web-liveness 既有）
- 服务恢复后页面自动刷新（web-liveness 既有 rev 比对）
- 刷进未就绪窗口 → 开机自检 13s 内自愈（web-liveness 既有，2026-09-22 上线）

## 非目标

- 不做 git 操作（不建 wip、不回滚、不合并）——发版场景仍走 `self_restart`
- 不做失败自动重试——避免重蹈 tmp-restart 死循环（2026-09-23 事故）
- 不改变 web-liveness client 半任何代码

## 设计

### 分工

| 工具 | 场景 | git | 回滚 | 续跑 |
|---|---|---|---|---|
| `quick_restart`（本 RFC） | 轻量重启：改动生效、异常自救 | 不动 | 无 | 无 |
| `self_restart`（lifecycle） | 发版：改代码→验证→合并 | wip 检查点 | 启动失败自动回滚 | pending-resume 注入 |

### 架构：只编排，不实现

```
agent 调用 quick_restart(reason)
  → web-liveness host 半（新增第一个工具）：
      1. 护栏检查（见下）
      2. 写 state/quick-restart-request.json {reason, requestedAt}
      3. spawn scripts/quick-restart.sh（detached + stdio ignore）
      4. 立即返回「已安排，约 10 秒后断线重启」
  → scripts/quick-restart.sh（新，~50 行 bash）：
      sleep 10（给 agent 留时间说完话、落盘会话）
      → ./scripts/stop.sh          ← 唯一入口，零自实现
      → nohup ./scripts/start.sh </dev/null >> log &
      → curl 轮询 http://127.0.0.1:13080/ 直到非 000（120s 超时）
      → 写 state/quick-restart-result.json {status: ok|failed, reason, at}
```

**原则**：杀与起的逻辑零自实现，全部委托 stop.sh/start.sh（2026-09-22 裁定的唯一入口）。
quick-restart.sh 只是同一入口的"远程遥控器"，不是新的重启路径。

### 护栏（host 工具内，spawn 前检查）

1. **互斥**：`state/restarting.lock` 新鲜（<15min）→ 拒绝（self_restart 进行中）
2. **限流**：距上次 quick_restart 不足 300s → 拒绝（state/quick-restart-request.json 时间戳）
3. **结果可见**：返回中附带上次重启结果（quick-restart-result.json），failed 时提示人工介入

### agent 使用契约（写进工具描述）

**先把要对用户说的话说完，本工具必须是本轮最后一个动作**——调用后约 10 秒服务断线，
当前 turn 若还没结束会被杀死（轻量工具无续跑机制）。页面会自动刷新恢复。

## 错误处理

| 失败点 | 行为 |
|---|---|
| 护栏拒绝 | 工具返回错误，不 spawn，无副作用 |
| stop.sh 失败 | 脚本记录日志并退出，结果文件写 failed |
| start.sh 120s 不起 | 结果文件写 failed + 日志路径，**不重试**，等人工 |
| spawn 本身失败 | 工具返回错误，锁不残留（spawn 前不写锁） |

## 测试

- 单测：限流/互斥判定纯函数（`quickRestartAllowed(lastAt, now, minIntervalMs)`、lock 新鲜度）——29/29 通过
- 冒烟：plugin-schema.smoke.test.ts 覆盖新工具 schema（web-liveness 加入 PLUGINS 列表）——21/21 通过
- 活体验证：合并后直接跑一次 `scripts/quick-restart.sh`，确认 10s 断线→自动拉起→HTTP 恢复→结果文件 ok——已跑通

## 实施后记（首跑踩坑）

- **健康判定假阳性（278a9e53 已修）**：`code=$(curl ... || echo 000)` 在连接拒绝时拼出 `000000`
  （curl 的 `-w %{http_code}` 失败也打印 000，退出码非零再触发 `|| echo 000`），`!= "000"` 误判为
  健康。改为 `|| code=000` + 三位长度校验。教训：curl 的 `-w` 输出与退出码是两条独立通道，不能叠加兜底。
- **冒烟 stub 连锁**：给 stubCtx 补 `inject` 后，lifecycle 的 webServer 注入回调开始真实执行，
  暴露出 stub 缺 `effect`/`webServer`——已一并补齐。
