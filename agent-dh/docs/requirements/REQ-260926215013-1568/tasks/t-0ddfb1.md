# t-0ddfb1 回合状态机：空闲才起轮、准入才计数、上限写终态

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
回合状态机：空闲才起轮、准入才计数、上限写终态

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/dive-round-driver.test.ts 全绿：连发 3 次触发只执行 1 次驱动体；驱动体抛错不产生未捕获异常/未处理 rejection；需求 version 变化后 pre-step 返回 reject 且同批消息被放回；checkpoint 失败后 activation 等于 disarmed；roundsInStage 等于 maxRounds 时 phase 等于 paused 且 pausedReason 等于 round-limit。

## 实施方案（implementation）
新增 src/application/dive/round-driver.ts：createDiveRoundDriver(ports) 实现 onIdle/onPreStep/onInboxInserted|Claimed|Discarded/onAgentError/onAgentDisposed/onRequirementMoved/onSessionEvent/requestDrive/teardown/whenQuiet；requestDrive 用 ports.agents.withoutInitiator 串 while(requested && !stopping) 单链；drive() 按设计 7 步（含排队点 await checkpoint() 屏障）；onPreStep 前后各一次 roundReservationValid + restoreOtherClaimed；admission 落 dive-round-admitted、终态落 dive-terminal-block、异常/检查点失败落 dive-disarm。新增 tests/dive-round-driver.test.ts（fake 端口）。

## 上游产出摘要（dependsSummary）
- 契约定死：回合来源、相位值域与驱动状态纯判定

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-26T14:39:22.616Z，窗口 session-c5ea210f-afc3-4735-a4d1-f9058b378363）

续跑现在按 Goal 的规矩起轮了：只有整窗口空闲且没有别人插队在先时才会起一轮，起轮前先确保台账落盘；回合只有真正进入对话历史才计入消耗，到上限写成看得见的终态，而不是刷一行日志就静默停跑。

### 完成项

- 新增 application/dive/round-driver.ts（399 行）：一个 agent 一个 DriverState（attempt/competingQueued/needsCheckpoint/requested/run/stopping）
- FR-1 pre-step 前后各校验一次 + 同批已认领消息按原序放回；FR-2 inbox 竞争让位；FR-3 排队点耐久检查点；FR-4 withoutInitiator 串行链 + requested 合并触发；FR-5 fail-closed teardown（全局 stopped 关准入）
- FR-7 准入才计数（user/message 身份匹配恰好 +1，discard 不计数）；FR-8 上限写终态 paused/round-limit + comment + 一次 warn；FR-9 max-tokens/aborted/error/disposed 各自收尾；FR-11 全路径 warn/comment 留痕
- round-state.ts 增补宿主结构访问器（agentIdOf/inboxOf/sourceOf 等，零框架依赖）
- 新增 tests/dive-round-driver.test.ts：11 条断言全绿（含 teardown 后触发不再排队、驱动体异常不产生未处理 rejection）
- 测试暴露并修复两个真实缺陷：teardown 后状态表清空导致新触发可重建状态 → 改全局 stopped；disarm 查需求时可能二次抛 → 加保护

### 改动文件

- `packages/web/dsh-pmboard/src/application/dive/round-driver.ts`
- `packages/web/dsh-pmboard/src/application/dive/round-state.ts`
- `packages/web/dsh-pmboard/tests/dive-round-driver.test.ts`

### 下一步

T-3 投递适配（AgentDeliverer 实现 DiveRoundDeliveryPort）→ T-4/T-5 接线

---
