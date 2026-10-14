# t-1e2f5e 端到端验收：触发 → 库有码 → 卡有理由（含唤醒量回归锁）·校验

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
端到端验收：触发 → 库有码 → 卡有理由（含唤醒量回归锁）·校验

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
校验项逐条给出结果：`npx vitest run tests/` → 全绿；异常项已列出并标注影响面

---
## 汇报 1（2026-10-07T11:21:54.770Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t13 校验段完成：端到端 5 passed，唤醒量锁与两条结构判据齐备。

### 完成项

- e2e（真规则 + 真触发行 + 真渲染器，只桩行情与外发传输）：5 passed，notify-guard intercepted=0 egress=0
- 断言链：事件带码 == 库中行带码；恰好 2/4 条进队列（唤醒量锁）；叫了的卡有升级原因、没叫的卡不多一行
- 不破现状全套 81 passed（checker / metric_contract / disposition ×2 / engine）
- 结构判据 2 passed：L2 比较点白名单（3 处非判定路由）+ 陈旧文案 0 命中
- 测试库零残留（rules 0 / triggers 0）
- 过程中踩到并修掉三处自身缺陷：假规则 id 撞外键、四条同标的互相去重、notifier 少传 trigger_repo 导致不落库

### 改动文件

- `tests/application/test_watch_escalation_e2e.py`

### 下一步

父卡 t-8097f7 收尾；13 张卡全完成后需求自动进入验收。

---
