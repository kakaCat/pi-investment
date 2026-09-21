# 诊断测试指南（T2: t-29e204）

## 目标
在 unbound 窗口触发诊断日志，找到 Hook 注入链路的断链位置

## 前置条件
✓ 5 个节点的诊断日志已添加
✓ DSH 服务已重启（PID 58761），新日志已加载

## 测试步骤

### 1. 打开新的 unbound 窗口
- 访问 http://127.0.0.1:13080
- 点击 "New Chat" 创建新会话
- 确认该窗口未绑定任何需求（reqboard_status 应显示 bound: false）

### 2. 发送测试消息
在新窗口中发送：
```
修复股票池刷新逻辑
```

### 3. 收集诊断日志
打开终端，实时监控日志：
```bash
tail -f ~/.dsh-data/state/launchd.out.log | grep "NODE-"
```

或者使用 tmux/screen 分屏查看

### 4. 分析日志输出

预期看到 5 个节点的日志（按顺序）：
- [NODE-1]: Hook subscription SUCCESS/FAILED
- [NODE-2]: user/message event ARRIVED
- [NODE-3]: pendingCapture SET
- [NODE-4]: systemPrompt assemble (pending=EXISTS/NONE)
- [NODE-5]: captureSectionText returns DYNAMIC PROMPT / returns ''

### 5. 断链位置判定

| 观察到的情况 | 断链位置 | 可能原因 |
|-------------|---------|---------|
| 节点1无日志 | Hook 订阅失败 | sessionEventCtx.on 未返回 disposer |
| 节点2无日志 | 事件未到达 | session/event 未被正确派发 |
| 节点3显示 shouldCapture:false | 窗口判定问题 | isWindowBound/hasPendingSuggestion 误判 |
| 节点4显示 windowKey:undefined | 提取失败 | windowKeyFromContext 逻辑问题 |
| 节点4显示 pending=NONE（但节点3已SET） | 状态不一致 | snapshot() 时序问题或 Map 引用问题 |
| 节点5返回空串（但前4正常） | 提示词生成问题 | captureSectionText 逻辑问题 |
| 全部正常但 Agent 未调用 reqboard_capture | LLM 忽略提示 | 提示词强度不足（非断链问题） |

## 当前限制
⚠️ 当前会话窗口（session-49bdb1dd）已绑定 REQ-f6307c，无法用于测试 unbound 逻辑
⚠️ 需要在 **新窗口** 中执行测试

## 下一步
测试完成后，将日志保存到 docs/requirements/REQ-f6307c/diagnostic-log.txt
