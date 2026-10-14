# t-8ccf53 补齐设计登记的未覆盖用例（run_forever 整环 / 跳过留痕去重 / 装配失败降级）·复核

> 需求：REQ-261007101318-c392 盯盘触发：休市日闸门缺失 + 通知缺股票名称

## 在做什么
补齐设计登记的未覆盖用例（run_forever 整环 / 跳过留痕去重 / 装配失败降级）·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/REQ-261007101318-c392/design/` 逐条核对；`npx vitest run tests/` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-07T05:53:47.407Z，窗口 session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544）

t5 复核段完成：变异测试证明新用例可证伪（拆掉闸门即转红），结论无偏离。

### 完成项

- 可证伪性反向验证（变异测试）：把 run_forever 的日级门临时替换为恒真后，test_run_forever_does_not_tick_on_holiday 立刻 1 failed
- 还原后自检 7 passed；engine.py 字节级还原（git diff --stat 仍为 +85/-9，未改坏）
- 逐条核对可行否性：三条新用例均断言具体行为（调用序列 / 去重条数 / repository 为 None），无一条只断言 not raises
- 对照 design/test-cases.md §6：三项未覆盖（run_forever 整环、留痕去重、装配降级）均已补
- 结论：无偏离

### 下一步

交测试子卡 t-094f32：跑 t5 验收命令并核对总数 ≥ 基线

---
