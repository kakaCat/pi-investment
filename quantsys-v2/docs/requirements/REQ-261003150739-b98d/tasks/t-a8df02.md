# t-a8df02 回归锁 + 切换 fail 模式并验证回滚·复核

> 需求：REQ-261003150739-b98d 修复 pytest 向真实通知渠道发消息（打桩点漂移）

## 在做什么
回归锁 + 切换 fail 模式并验证回滚·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-03T07:16:10.303Z，窗口 session-06404018-404f-4c74-b75d-0e786a1bb5d7）

复核段完成：反向验证确认真能抓住漂移，且仍然零外发。

### 完成项

- 复刻旧漏点后用例失败并打出目标 URL
- intercepted=2 但 egress=0（拦截在先）
- 临时探针文件已删除

### 改动文件

- `tests/notify_guard.py`
- `tests/test_notify_guard.py`
- `conftest.py`

---
