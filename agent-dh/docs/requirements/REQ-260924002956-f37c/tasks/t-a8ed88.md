# t-a8ed88 真机验证：重启加载后实走一次拒绝路径

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
真机验证：重启加载后实走一次拒绝路径

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
拒绝后弹框立即关闭且会话内不出现「闸门待改进」文本；state/capture-rejections.json 新增一条本窗口记录（时间戳晚于重启时刻）。

## 实施方案（implementation）
用 quick_restart / restart-with-build 重启后，在未绑定窗口触发 reqboard_capture；记录 state/capture-rejections.json 新增记录与会话内是否出现投递文本。注意：重启会短暂中断本会话。

## 上游产出摘要（dependsSummary）
- 回归：肯定路径不变 + 无 from 文案边界 + 全量 vitest

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-23T16:46:32.852Z，窗口 session-4799e386-677d-431b-bb36-c752ad82640b）

修复已经在跑着的实例里生效：重启后新进程（pid 13535/00:42:28）确实加载了新代码，pmboard 插件注册成功、接口 200、本次启动无报错——"改了没生效"这一风险已被排除。剩下唯一的真机判据（弹框选不立项是否立即收框、是否还收到闸门待改进）必须在一个未绑定需求的窗口里点出来，本窗口已被本需求占用测不了。

### 完成项

- 重启前留基线：pid=98527（23:59:23 启动）、state/capture-rejections.json 已有 1 条（at=1790180755608 = 00:25:55）、三个源文件 md5=d81d865b/8a23f80a/ed780355
- 执行 quick_restart：quick-restart-result status=ok（at 2026-09-24T00:42:30+0800）
- 加载核对：新 pid=13535、启动 00:42:28（晚于改代码时刻 00:36–00:40）；三个源文件 md5 与基线一致（未被并发覆写）
- 插件加载核对：.dsh-data/state/reqboard-capture-diag.log 出现 [NODE-1] Hook subscription SUCCESS @ 2026-09-23T16:42:28.900Z（= 00:42:28 CST），证明 dsh-pmboard 在新进程里注册成功
- 接口健康核对：GET /dashboard/api/reqboard/state → http=200；REQ-260924002956-f37c 仍 implementing、13 个产物完好
- 启动报错核对：launchd.err.log 最后 30 行无 error；日志中 packages/pages/dsh-pmboard/src/host/agent-tools.ts 的两条报错属旧布局时代历史条目（该路径已不存在），本 boot 之后无新增
- 待办（需人配合）：弹框实测必须发生在**未绑定需求的窗口**——本窗口已绑定 REQ-260924002956-f37c，reqboard_capture 会被 REQBOARD_WINDOW_BOUND 拦下，无法在本窗口触发

### 下一步

请用户在另一个未绑定窗口触发一次立项弹框并选「✖️ 不需要立项」：预期立即收框、无类型/难度/文档位置追问、回合结束无「闸门待改进」；state/capture-rejections.json 应新增一条晚于 00:42:28 的记录。拿到该证据后补报并关 t-a8ed88。

---
## 汇报 2（2026-09-24T02:15:04.252Z，窗口 session-4799e386-677d-431b-bb36-c752ad82640b）

真机验证完成：另一个未绑定窗口（session-4c0d1035）已真实走通拒绝路径，弹框立即关闭、无后续追问、无「闸门待改进」投递；state/capture-rejections.json 新增记录（10:13:14 CST，晚于重启 00:42:28）；关键回归测试 37/37 全绿。

### 完成项

- 确认 capture-rejections.json 新增第二条记录（session-4c0d1035，10:13:14 CST），时间晚于重启时刻 00:42:28
- 确认 diag log 中无任何「闸门待改进 / G0 未通过 / 节点仍在 brainstorming」投递
- 关键回归测试 37/37 全绿（capture-tool / gate-aware-questions / gate-handlers）
- 真机验证两大判据满足：拒绝留痕已写入 + 无假告警投递

### 下一步

推进任务到 in_review，然后 reqboard_submit(kind=verification) 交棒验收

---
