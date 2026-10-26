# t-e1eb49 建交易包中立成交端口并保留旧路径转发·复核

> 需求：REQ-261021194640-69b8 盯盘执行闭环三接缝：成交回写·消息投递·待办闭环

## 在做什么
建交易包中立成交端口并保留旧路径转发·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/REQ-261021194640-69b8/design/` 逐条核对；`npx vitest run tests/` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-21T12:15:21.582Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

复核结论：无实质偏离。契约四项（端口中立、注册注销、旧 import 等价、notify_fill 失败不反噬）逐条有实现与用例支撑；唯一差异是 notify_fill 的实例级 listener 覆盖参数，属 additive。

### 完成项

- IF-1 字段核对：FillEvent 11 字段与 to_dict 投影一致，frozen 不可变
- IF-2 语义核对：未注册返回 False 不告警、有监听返回 True、监听异常吞掉只记日志
- 中立性核对：端口仅注释提及 watch，无 import；旧路径与端口为同一对象且共享注册位
- 偏离说明：notify_fill 增加 keyword-only listener 参数为实例级覆盖（additive，设计 IF-2 未禁止）
- 卡面模板的 npx vitest 不适用本 Python 仓，复核以 pytest 24 例为准

### 改动文件

- `../../packages/qs_trading/qs_trading/application/ports/fill_listener.py`
- `../../application/trading/paper_trading_engine.py`

### 下一步

测试段：复跑验收与相邻回归，登记读数

---
