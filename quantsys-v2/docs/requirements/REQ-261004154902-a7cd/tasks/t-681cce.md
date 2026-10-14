# t-681cce 探活加调度活性并新增「该跑没跑」盘点器·测试

> 需求：REQ-261004154902-a7cd V13 策略实现缺陷排查（因子/模型/调仓/止损全链路取证）

## 在做什么
探活加调度活性并新增「该跑没跑」盘点器·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-04T08:37:01.561Z，窗口 session-8eb5b6f2-0d2a-44d3-bfca-878578124cec）

测试子卡：26 条用例全绿，三条验收命令逐条给出真实输出，且零外发。

### 完成项

- venv/bin/python -m pytest tests/test_should_have_run.py -q → 26 passed
- venv/bin/python tools/check_should_have_run.py → 五列表格完整、退出码 0（11 张启用任务、无法判定 0）
- 验收第三条：把盘点时刻设为次日的对应时刻，真漏跑即判 missed 且退出码 2（护栏自清，证明判据有效）
- 观察模式：默认不外发、退出码不受影响；打开开关才计入不健康（两种行为各有用例）
- launchd 守护实测已用新代码跑过一轮，未触发任何外发；状态文件里已提醒键为空（零压制）
- 会话末 notify-guard：intercepted=0 egress=0

### 改动文件

- `tests/test_should_have_run.py`

---
