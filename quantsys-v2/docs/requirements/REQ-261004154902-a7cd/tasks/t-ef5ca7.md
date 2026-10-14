# t-ef5ca7 端到端冒烟与验收证据汇总·测试

> 需求：REQ-261004154902-a7cd V13 策略实现缺陷排查（因子/模型/调仓/止损全链路取证）

## 在做什么
端到端冒烟与验收证据汇总·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-04T08:52:30.155Z，窗口 session-8eb5b6f2-0d2a-44d3-bfca-878578124cec）

测试子卡：验收命令退出码 0、全量回归干净，验收材料落盘。

### 完成项

- venv/bin/python tools/check_v13_chain_health.py → 退出码 0，三张表均有真实行（11 张调度任务 / 4 只超卖与挂单分布 / 通知计数）
- 同一条命令加 --json 可机器读（同一份判定，不另算一遍）
- 全量回归（非 e2e）：6257 passed / 1 failed（分层计数，非本需求引入）/ 3 errors（既有环境问题），较开工时净增 134 条通过
- 验收材料已汇总为 docs/requirements/REQ-261004154902-a7cd/verification.md（逐条 FR 附命令与输出摘要）
- 会话末 notify-guard：intercepted=0 egress=0

### 改动文件

- `docs/requirements/REQ-261004154902-a7cd/verification.md`

---
