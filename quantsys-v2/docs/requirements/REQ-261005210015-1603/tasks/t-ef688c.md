# t-ef688c fitness 服务诚实计数：四类状态 + accounts_total，删 skipped、收窄 computed 语义·测试

> 需求：REQ-261005210015-1603 修复每日任务完成通知误导（耗时 0.0 分钟 / computed 语义 / 全 NULL 仍报 ✅）

## 在做什么
fitness 服务诚实计数：四类状态 + accounts_total，删 skipped、收窄 computed 语义·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-05T13:16:02.339Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

测试段：服务层用例全过，计数不变式与兼容锁实测成立

### 完成项

- 服务层用例全过：pytest tests/services/evolution/test_evolution_fitness_service.py -q（含 1 条既有 skip）
- 计数不变式实测：2 ok、1 no_trades、1 data_gap → 四类加 other 等于 accounts_total 等于 4
- 兼容锁实测：computed 等于 accounts_total，且返回体不含 skipped 键
- 正式增补用例归父卡 t-89b1f4 创作，本卡只做本阶段验证

### 下一步

父卡 t-c0941a 收尾；正式用例由 t-89b1f4 承载

---
