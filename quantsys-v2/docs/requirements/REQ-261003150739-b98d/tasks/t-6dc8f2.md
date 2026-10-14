# t-6dc8f2 回归锁 + 切换 fail 模式并验证回滚·测试

> 需求：REQ-261003150739-b98d 修复 pytest 向真实通知渠道发消息（打桩点漂移）

## 在做什么
回归锁 + 切换 fail 模式并验证回滚·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-03T07:16:10.772Z，窗口 session-06404018-404f-4c74-b75d-0e786a1bb5d7）

测试段完成：三文件与守卫单测全过，回滚开关有效。

### 完成项

- 三文件 36 passed，汇总 egress=0 offenders=[]
- 守卫单测 13 passed
- QUANTSYS_NOTIFY_GUARD=off 重跑仍全过

### 改动文件

- `tests/notify_guard.py`
- `tests/test_notify_guard.py`
- `conftest.py`

---
