# reqboard 立项弹框（capture）排障指南

> 来源：REQ-f6307c（2026-09-21）。适用症状：用户在 unbound 窗口发了工作意图消息，但立项弹框（reqboard_capture）没弹。

## 第一原则：先查诊断文件，不要只看 stdout

**可靠观测面**：`agent-dh/.dsh-data/state/reqboard-capture-diag.log`

```bash
tail -f agent-dh/.dsh-data/state/reqboard-capture-diag.log
```

⚠️ **不要只依赖 stdout/控制台日志**（REQ-f6307c 的核心教训）。stdout 在以下情形全部蒸发：

- launchd 未接管当前进程（被外部 shell 手工 `start.sh` 拉起）
- 进程由 `start.sh 2>&1 | tail -5` 这类管道拉起、reader 退出后 stdout 成死管道
- 查错日志路径：launchd 配置的真实路径是 `.dsh-data/state/launchd.out.log`，不是 `~/Library/Logs/`

判别进程 stdout 是否死管道：`lsof -p <pid> -a -d 1,2`——显示 PIPE 且对端无进程即死管道。

## 链路 5 节点速查表

| 标记 | 位置 | 正常输出 | 异常含义 |
|------|------|---------|---------|
| EARLY | apply() 开头 | `apply function STARTED` | 无此行 = 插件未加载（查 cordis 配置） |
| NODE-1 | Hook 订阅 | `Hook subscription SUCCESS (unsubscribe=function)` | FAILED = `ctx.on` 未注册成功 |
| NODE-2 | user/message 到达 | `user/message event ARRIVED (windowKey=...)` | 无此行 = 事件未派发（或消息没真发出去——查 sessions 目录是否有写入） |
| NODE-3 | pendingCapture 填充 | `pendingCapture SET (size=N, text.length=M)` | 无此行 = 窗口 bound / 有遗留 pending / 消息被清洗为空 / 非 direct-human |
| NODE-4 | systemPrompt 组装 | `systemPrompt assemble (windowKey=..., pending=EXISTS/NONE)` | windowKey=undefined = 上下文提取失败 |
| NODE-5 | 提示词生成 | `DYNAMIC PROMPT (text.length≈1179)` / `STATIC GUIDANCE (620)` / `'' (reason=...)` | 返回空串看 reason：windowBound / hasPendingSuggestion / windowKey=undefined |

## 常见误判

1. **"日志没有 = 代码没跑"是错的**：先确认你看的日志通道本身可靠（见第一原则）。REQ-f6307c 曾因此误诊"apply() 未执行"，实际链路完全正常。
2. **pending 长时间不清除不是 bug**：pending 在 turn/end 才清除；弹框等待作答、Agent 长回合期间 pending 存活属设计内（回合内持续 nag 提醒）。回合结束后看 NODE-4 的 size 是否回落 0。
3. **"弹框没弹"先排除消息没发出去**：重启前打开的浏览器标签页 WebSocket 可能已断，页面看着正常但消息发不出。判据：`find .dsh-data/sessions -mmin -5` 应有新写入；发消息后窗口应有"转圈"动画。
4. **investor-session（定时任务会话）只出现 STATIC GUIDANCE 属正常**：系统注入消息经清洗后不计入捕获。

## 验证脚本（可复核）

```bash
cd agent-dh/packages/pages/dsh-pmboard
node --import tsx/esm scripts/verify-capture-chain.mts   # 集成链路（真实 ledger）
node --import tsx/esm scripts/verify-t4-rounds.mts      # 连续 3 轮 + turn/end 清除
```

两者都应输出 PASS。失败时对照上方 5 节点表定位。