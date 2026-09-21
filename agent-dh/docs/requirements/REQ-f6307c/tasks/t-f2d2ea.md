# t-f2d2ea 根据诊断结果修复 Hook 注入链路

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
根据诊断结果修复 Hook 注入链路

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

怎么验（可执行）：
1. 命令：cd agent-dh/packages/pages/dsh-pmboard && node --import tsx/esm scripts/verify-capture-chain.mts → 输出 "PASS：unbound 全链路通畅"，DYNAMIC PROMPT text.length=1179>0
2. 命令：grep -E "NODE-1.*SUCCESS|DYNAMIC PROMPT" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 真实环境 5 节点日志齐全
3. 界面路径（用户已于 2026-09-21 10:31 实测确认）：新开 unbound 窗口发工作意图消息 → Agent 弹出立项三问弹框（reqboard_capture 首调）

## 实施方案（implementation）
根据 T2 诊断结果选择修复方向：A.windowKey提取失败(gate-wiring.ts)、B.snapshot状态不一致(CaptureHook.ts生命周期)、C.判断逻辑误判(window.ts shouldCaptureWindow)、D.事件订阅失败(index.ts订阅逻辑)。最小化改动，添加防御性检查，保留诊断日志

## 上游产出摘要（dependsSummary）
- 执行诊断测试，找到链路断链位置

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T10:26:50.723Z，窗口 session-49bdb1dd-08e1-4ac1-a28a-daf1db28f99a）

这一步做完，变化是：①推翻了 T2 的误诊——Hook 链路从来没有断，"apply 未执行"是三重观测面错误（查错日志路径 / launchd 日志停更 / stdout 进了死管道）造成的假象；②诊断日志从此有了可靠落点——新增文件化诊断通道 captureDiag（双写到 state/reqboard-capture-diag.log），5 个节点全部改用双写，今后排查不再依赖可能蒸发的 stdout；③用真实环境日志 + 集成验证双重证实链路全通：unbound 窗口会注入 1179 字符的动态提示词（含"第一个工具调用必须是 reqboard_capture"），bound 窗口正确零噪音。

### 完成项

- 推翻 T2 误诊：三重观测面错误取证（plist 真实日志路径 / launchd.out.log 停更于 09-19 / 当前进程 stdout 为无读者管道），并给出 apply 一直在正常执行的 3 条反证
- 新增 src/application/internal/diag-log.ts：captureDiag 文件+控制台双写，512KB 轮转，失败静默不挡主流程
- 5 个诊断节点 + EARLY 全部切换为 captureDiag 双写（index.ts / CaptureHook.ts / gate-wiring.ts / capture-section.ts）
- self_restart 加载新代码后验证：diag 文件实录 EARLY + NODE-1(SUCCESS) + NODE-2 + NODE-4 + NODE-5，真实环境链路通畅
- 集成验证 scripts/verify-capture-chain.mts（真实源码+真实 ledger）：unbound 全链 NODE-2→3→5 DYNAMIC PROMPT 1179 字符、无 pending STATIC 620 字符、bound 空串，判定 PASS
- 诊断文档 diagnostic-log.txt 重写：误诊修正 + 修复动作 + 验证实录
- wip checkpoint 已合并回 main（merged 699319d3）

### 改动文件

- `agent-dh/packages/pages/dsh-pmboard/src/application/internal/diag-log.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/index.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/gate-wiring.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/application/internal/capture-section.ts`
- `agent-dh/packages/pages/dsh-pmboard/scripts/verify-capture-chain.mts`
- `agent-dh/docs/requirements/REQ-f6307c/diagnostic-log.txt`

### 下一步

T4（t-9470a3）连续测试与回归验证：需人工配合在 3 个新 unbound 窗口分别发送工作意图消息，确认 Agent 首调 reqboard_capture（本步已证明提示词会注入，剩最后一环需真实 LLM 回合）

---
