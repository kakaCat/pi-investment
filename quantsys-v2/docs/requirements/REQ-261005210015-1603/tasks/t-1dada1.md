# t-1dada1 空转读数：EvolutionFitnessORMRepository 两个只读聚合方法·复核

> 需求：REQ-261005210015-1603 修复每日任务完成通知误导（耗时 0.0 分钟 / computed 语义 / 全 NULL 仍报 ✅）

## 在做什么
空转读数：EvolutionFitnessORMRepository 两个只读聚合方法·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-05T13:15:40.781Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

复核段：只读性、索引与口径边界核对无偏离

### 完成项

- 只读性复核：两方法仅用分组、排序、限行与 max 聚合，无 add、无 commit、无 update
- 索引复核：查询按 window_end 过滤与分组，表上已有 idx_evolution_fitness_window_end
- 口径边界复核：按 window_days=20 过滤避免混口径；从未有 ok 时 max 返回 None，消息侧回落为「从未」
- 规模复核：当前 280 行、56 个 window_end，两条聚合为毫秒级
- 无偏离设计：只读、不加列、不改 DDL

### 下一步

测试段补两条只读口径用例（倒序计数与忽略非 ok）

---
