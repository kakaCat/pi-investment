# t-bc7a9b 回归 + 真实休市日/复市首日观察·测试

> 需求：REQ-261005203907-2b8c DailyJobs 宿主接入交易日门：休市日不再开火（pool_daily_refresh 等）

## 在做什么
回归 + 真实休市日/复市首日观察·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
四条命令退出码 0 且输出与 notes/holiday-observation.md §1/§2 记录一致（27 / 6 / 37 passed + 台账查询）；notes 含实际输出与待观察项；会话末 notify-guard 行 egress=0、offenders=[]。注：卡上原写的 pnpm test / npx tsc 属 JS 栈模板，本仓为 Python，已按等价命令修订。

---
## 汇报 1（2026-10-05T13:25:20.240Z，窗口 session-b97ce139-00d0-456f-b147-6b897bcb5369）

测试阶段：四条验收复跑均与记录一致（27 / 6 / 37 passed + 台账基线），通知守卫零外发。

### 完成项

- 复跑 ① → 27 passed（与记录 §1 一致）
- 复跑 ② → 6 passed（与记录 §1 一致）
- 复跑 ③ → 37 passed（与记录 §1 一致）
- 复跑 ④ 台账 → 与记录 §2 一致；evening_pipeline 仍 running（54.3 分钟，比记录时点 +0.9 分钟）、chip_distribution 仍 running（14.4 分钟）
- 四次运行 notify-guard 均为 intercepted=0 egress=0 offenders=[]

### 下一步

父卡收尾；随后提交验收材料（reqboard_submit kind=verification）。

---
