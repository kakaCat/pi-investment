# t-cab4a2 会话驱动器组合：一拍内的定序与原采集行为不变（含向后兼容）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
会话驱动器组合：一拍内的定序与原采集行为不变（含向后兼容）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts 全绿（不注入 round 端口时行为与改动前一致）；wc -l src/application/dive/session-driver.ts 输出行数不超过 400。

## 实施方案（implementation）
抽出 src/application/dive/idle-capture-actions.ts（withAddressSection/milestoneReminderFor 逐字搬移）；src/application/dive/session-driver.ts 增可选 deps.round（DiveRoundDriver），onAgentStatus(idle) 内按「复位 competingQueued → 采集跑批 → requestDrive」定序，session/event 尾部调 round.onSessionEvent；不注入 round 时退化为原行为（旧调用方兼容）。

## 上游产出摘要（dependsSummary）
- 回合状态机：空闲才起轮、准入才计数、上限写终态

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-26T14:40:58.128Z，窗口 session-c5ea210f-afc3-4735-a4d1-f9058b378363）

采集与续跑现在在同一拍里按固定次序协作：先复位「有人插队」标志，再跑采集（该注入的纪律照旧注入），最后才请求起轮。没有注入续跑端口时行为与改动前完全一样，所以老调用方、脚本和现有测试都不受影响。

### 完成项

- 抽出 application/dive/idle-capture-actions.ts（addressSectionFor / milestoneReminderFor，逐字搬移，纯函数）
- session-driver.ts 增可选 deps.round（DiveRoundDriver）：onAgentStatus(idle) 按「round 复位 competingQueued → 采集跑批 driveIdle → requestDrive」定序
- session/event 尾部把事件转交 round 半做回合簿记（admission / turn-end 收尾）
- deps.round 缺省 = 纯采集/簿记（与改动前逐字一致，向后兼容）
- session-driver.ts 从 397 行降到 356 行（尺寸门禁内，为 round 半接线腾出空间）

### 改动文件

- `packages/web/dsh-pmboard/src/application/dive/session-driver.ts`
- `packages/web/dsh-pmboard/src/application/dive/idle-capture-actions.ts`

### 下一步

T-5 Dive 服务接线（manager 持有全部订阅 + 组合根注入 round 端口）

---
