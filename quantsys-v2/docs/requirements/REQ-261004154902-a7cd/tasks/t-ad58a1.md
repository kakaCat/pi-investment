# t-ad58a1 端到端冒烟与验收证据汇总

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
端到端冒烟与验收证据汇总

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果
venv/bin/python tools/check_v13_chain_health.py 退出码 0 且三张表均有真实行；验收材料含每条 FR 的可复核证据（命令 + 输出摘要 + 路径）；restore 检查：v13 任务恢复为 is_enabled=true 且 cron=30 14 * * 1-5（止血记录里的原值已按设计改写）。

## 实施方案（implementation）
新增 tools/check_v13_chain_health.py（只读，一条命令输出三张表：①应跑未跑/被跳过 ②当日成交与拒绝原因分布 ③通知送达与失败分类）；把一个交易日内的真实冒烟结果、日志证据与命令输出汇总成验收材料（reqboard_submit(kind=verification) 的 evidence）。

## 上游产出摘要（dependsSummary）
- 策略日检如实上报并修回通知方法
- 交易日判定收敛到日历链
- 挂单撮合批量不中断、时段护栏与过期收口
- 调度失败的飞书兜底与告警覆盖面
- 探活加调度活性并新增「该跑没跑」盘点器
- 修通知渠道收窄并补齐缺失的飞书 formatter
- 收敛策略配置为单一来源并让生效值可见
- 修实未接线链路并删掉锁死 bug 的假断言
- 历史虚增现金标记为脏并从统计排除（按用户裁定）
- 假绿灯结构门禁

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-04T08:52:30.275Z，窗口 session-8eb5b6f2-0d2a-44d3-bfca-878578124cec）

主卡：链路健康第一次能被一条命令看见，且验收材料逐条可复核。

### 完成项

- 主卡目标达成：一条只读命令即可看到这条链路的调度/交易/通知三面实况，退出码 0
- 止血恢复已核对：v13 任务启用、cron 恢复到 30 14 * * 1-5（本地 14:30）、宽限为空；jobstore 11 条任务在册
- 验收材料逐条对应 10 个功能点，每条都有命令与输出摘要，并如实登记 7 项残留
- 全量回归 6257 passed（唯一 failed 为他人引入的分层计数，3 errors 为既有环境问题）
- 所有改动已另存 patch 与快照备底（工作区状态可完整还原）

### 改动文件

- `tools/check_v13_chain_health.py`
- `docs/requirements/REQ-261004154902-a7cd/verification.md`

---
